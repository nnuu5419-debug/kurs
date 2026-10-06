import jwt
from fastapi import Depends, HTTPException, Request
from .config import settings
from .db import SessionLocal, User, Level, Purchase

def get_db():
    with SessionLocal() as db:
        yield db

def current_user(request: Request, db=Depends(get_db)) -> User:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        uid = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])["uid"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid session")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "User not found")
    return user

def require_admin(user: User = Depends(current_user)) -> User:
    # Re-checked against the DB on EVERY request (never trust the client/JWT for admin)
    if not user.is_admin:
        raise HTTPException(403, "Forbidden")
    return user

def has_access(db, user: User, level: Level) -> bool:
    if level.price_cents == 0:
        return True
    return db.query(Purchase).filter_by(user_id=user.id, level_slug=level.slug, status="paid").first() is not None
