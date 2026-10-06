import json, time, difflib, re
import jwt, requests, stripe
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google.oauth2 import id_token
from google.auth.transport import requests as g_requests
from openai import AsyncOpenAI

from .config import settings
from .db import init_db, User, Level, Purchase
from .deps import get_db, current_user, require_admin, has_access

app = FastAPI(title="Lingua API")
app.add_middleware(CORSMiddleware, allow_origins=[settings.FRONTEND_URL],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
stripe.api_key = settings.STRIPE_SECRET_KEY
ai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
MODEL = "gpt-4o"

@app.on_event("startup")
def _startup(): init_db()

def user_dto(u: User):
    return {"id": u.id, "email": u.email, "name": u.name, "picture": u.picture,
            "is_admin": u.is_admin, "level_estimate": u.level_estimate}

# ---------- 1. Auth: Google only ----------
class GoogleLogin(BaseModel):
    credential: str  # Google ID token from Google Identity Services

@app.post("/auth/google")
def google_login(body: GoogleLogin, response: Response, db=Depends(get_db)):
    try:
        info = id_token.verify_oauth2_token(body.credential, g_requests.Request(), settings.GOOGLE_CLIENT_ID)
    except ValueError:
        raise HTTPException(401, "Invalid Google token")
    if not info.get("email_verified"):
        raise HTTPException(401, "Email not verified")
    email = info["email"].lower()
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(email=email)         # is_admin stays False
        db.add(user)
    user.name, user.picture = info.get("name", ""), info.get("picture", "")
    db.commit()
    token = jwt.encode({"uid": user.id, "exp": int(time.time()) + 7 * 86400}, settings.JWT_SECRET, "HS256")
    response.set_cookie("session", token, httponly=True, secure=settings.COOKIE_SECURE,
                        samesite="lax", max_age=7 * 86400)
    return user_dto(user)

@app.get("/auth/me")
def me(user: User = Depends(current_user)): return user_dto(user)

@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("session"); return {"ok": True}

# ---------- 2. Levels & content gate ----------
@app.get("/levels")
def levels(user: User = Depends(current_user), db=Depends(get_db)):
    return [{"slug": l.slug, "title": l.title, "price_cents": l.price_cents, "currency": l.currency,
             "unlocked": has_access(db, user, l)} for l in db.query(Level).order_by(Level.position)]

@app.get("/levels/{slug}/content")
def level_content(slug: str, user: User = Depends(current_user), db=Depends(get_db)):
    level = db.get(Level, slug)
    if not level: raise HTTPException(404, "Level not found")
    if not has_access(db, user, level):
        raise HTTPException(402, "Payment required")   # server-side lock, not just UI
    return {"slug": level.slug, "title": level.title, "lessons": level.lessons}

# ---------- Payments (Stripe Checkout) ----------
class CheckoutReq(BaseModel):
    level_slug: str

@app.post("/payments/checkout")
def checkout(body: CheckoutReq, user: User = Depends(current_user), db=Depends(get_db)):
    level = db.get(Level, body.level_slug)
    if not level: raise HTTPException(404, "Level not found")
    if has_access(db, user, level): raise HTTPException(400, "Already unlocked")
    session = stripe.checkout.Session.create(   # price read from DB at this moment => admin changes apply instantly
        mode="payment", customer_email=user.email,
        line_items=[{"quantity": 1, "price_data": {
            "currency": level.currency, "unit_amount": level.price_cents,
            "product_data": {"name": f"English – {level.title}"}}}],
        success_url=f"{settings.FRONTEND_URL}/level/{level.slug}?paid=1",
        cancel_url=f"{settings.FRONTEND_URL}/pay/{level.slug}",
        metadata={"user_id": str(user.id), "level_slug": level.slug})
    db.add(Purchase(user_id=user.id, level_slug=level.slug, stripe_session_id=session.id,
                    amount_cents=level.price_cents))
    db.commit()
    return {"url": session.url}

@app.post("/payments/webhook")
async def stripe_webhook(request: Request, db=Depends(get_db)):
    payload, sig = await request.body(), request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Bad signature")
    if event["type"] == "checkout.session.completed":
        p = db.query(Purchase).filter_by(stripe_session_id=event["data"]["object"]["id"]).first()
        if p: p.status = "paid"; db.commit()
    return {"ok": True}

# ---------- 3. Admin ----------
class PriceUpdate(BaseModel):
    price_cents: int = Field(ge=0, le=1_000_000)

@app.get("/admin/levels")
def admin_levels(_: User = Depends(require_admin), db=Depends(get_db)):
    return [{"slug": l.slug, "title": l.title, "price_cents": l.price_cents, "currency": l.currency}
            for l in db.query(Level).order_by(Level.position)]

@app.patch("/admin/levels/{slug}")
def admin_set_price(slug: str, body: PriceUpdate, _: User = Depends(require_admin), db=Depends(get_db)):
    level = db.get(Level, slug)
    if not level: raise HTTPException(404, "Level not found")
    if slug == "beginner" and body.price_cents != 0:
        raise HTTPException(400, "Beginner must stay free")
    if slug != "beginner" and body.price_cents < 50:
        raise HTTPException(400, "Paid levels need at least 0.50")
    level.price_cents = body.price_cents
    db.commit()           # /levels reads the DB on each request => change is live immediately
    return {"slug": slug, "price_cents": level.price_cents}

# ---------- 4. Video (Daily.co) ----------
@app.post("/video/room/{slug}")
def video_room(slug: str, user: User = Depends(current_user), db=Depends(get_db)):
    level = db.get(Level, slug)
    if not level or not has_access(db, user, level): raise HTTPException(402, "Payment required")
    h = {"Authorization": f"Bearer {settings.DAILY_API_KEY}"}
    name = f"lingua-{slug}"
    r = requests.get(f"https://api.daily.co/v1/rooms/{name}", headers=h, timeout=10)
    if r.status_code == 404:
        r = requests.post("https://api.daily.co/v1/rooms", headers=h, timeout=10,
                          json={"name": name, "privacy": "private", "properties": {"exp": int(time.time()) + 86400}})
    r.raise_for_status()
    t = requests.post("https://api.daily.co/v1/meeting-tokens", headers=h, timeout=10,
                      json={"properties": {"room_name": name, "user_name": user.name or user.email,
                                           "is_owner": user.is_admin, "exp": int(time.time()) + 7200}})
    t.raise_for_status()
    return {"url": f"{r.json()['url']}?t={t.json()['token']}"}

# ---------- 5. AI ----------
async def llm_json(system: str, user_msg: str | list) -> dict:
    msgs = [{"role": "system", "content": system}]
    msgs += user_msg if isinstance(user_msg, list) else [{"role": "user", "content": user_msg}]
    r = await ai.chat.completions.create(model=MODEL, messages=msgs, temperature=0.4,
                                         response_format={"type": "json_object"})
    return json.loads(r.choices[0].message.content)

class Msg(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=2000)

class TutorReq(BaseModel):
    messages: list[Msg] = Field(max_length=20)
    level: str = "beginner"

TUTOR_SYS = """You are a friendly English tutor for a {level} learner (native language may be Kyrgyz/Russian).
Reply in simple English suited to the level. Always answer as JSON:
{{"reply": "your conversational answer ending with a short follow-up question",
 "corrections": [{{"original": "...", "fixed": "...", "why": "short explanation"}}]}}
Only list real grammar/spelling mistakes from the learner's LAST message; empty list if none."""

@app.post("/ai/tutor")
async def tutor(body: TutorReq, user: User = Depends(current_user)):
    return await llm_json(TUTOR_SYS.format(level=body.level), [m.model_dump() for m in body.messages])

@app.post("/ai/placement/start")
async def placement_start(user: User = Depends(current_user)):
    data = await llm_json(
        "Create an English placement test. Return JSON {\"questions\":[{\"q\":str,\"options\":[4 strings],"
        "\"answer\":int(0-3),\"cefr\":\"A1|A2|B1|B2|C1\"}]} with exactly 15 grammar/vocabulary multiple-choice "
        "questions: 3 each for A1,A2,B1,B2,C1, ordered easy to hard.", "Generate the test.")
    qs = data["questions"][:15]
    sealed = jwt.encode({"key": [[q["answer"], q["cefr"]] for q in qs], "uid": user.id,
                         "exp": int(time.time()) + 3600}, settings.JWT_SECRET, "HS256")
    return {"token": sealed, "questions": [{"q": q["q"], "options": q["options"]} for q in qs]}  # answers never sent

class PlacementSubmit(BaseModel):
    token: str
    answers: list[int]

CEFR_TO_LEVEL = {"A1": "beginner", "A2": "elementary", "B1": "intermediate", "B2": "upper-intermediate", "C1": "advanced"}

@app.post("/ai/placement/submit")
def placement_submit(body: PlacementSubmit, user: User = Depends(current_user), db=Depends(get_db)):
    try:
        key = jwt.decode(body.token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(400, "Test expired")
    if key["uid"] != user.id: raise HTTPException(403, "Forbidden")
    stats: dict[str, list[int]] = {}
    for (ans, cefr), given in zip(key["key"], body.answers):
        stats.setdefault(cefr, []).append(int(ans == given))
    result = "A1"
    for c in ["A1", "A2", "B1", "B2", "C1"]:       # highest band with >=2/3 correct, stop at first failed band
        s = stats.get(c, [])
        if s and sum(s) / len(s) >= 0.6: result = c
        else: break
    user.level_estimate = CEFR_TO_LEVEL[result]; db.commit()
    return {"cefr": result, "level": user.level_estimate}

class PronReq(BaseModel):
    target: str = Field(max_length=300)
    transcript: str = Field(max_length=300)
    confidence: float = Field(ge=0, le=1, default=0.8)   # from Web Speech API

norm = lambda s: re.findall(r"[a-z']+", s.lower())

@app.post("/ai/pronunciation")
async def pronunciation(body: PronReq, user: User = Depends(current_user)):
    t, s = norm(body.target), norm(body.transcript)
    sm = difflib.SequenceMatcher(None, t, s)
    words = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            words += [{"word": w, "ok": True} for w in t[a1:a2]]
        else:
            words += [{"word": w, "ok": False, "heard": " ".join(s[b1:b2])} for w in t[a1:a2]]
    acc = sm.ratio()
    score = round(100 * (0.8 * acc + 0.2 * body.confidence))
    bad = [w["word"] for w in words if not w["ok"]]
    tips = {"tips": []}
    if bad:
        tips = await llm_json('Give pronunciation tips as JSON {"tips":[{"word":str,"tip":str}]} for a Russian/Kyrgyz '
                              'speaker. Short, practical, mention tongue/lip position.', f"Words: {bad}")
    return {"score": score, "words": words, **tips}
