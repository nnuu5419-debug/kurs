# Lingua – English learning platform

## Run
1. Google Cloud Console → OAuth Client ID (Web). Authorized JS origin: http://localhost:3000. Put it into both .env files.
2. `cp backend/.env.example backend/.env` and fill in keys; set ADMIN_EMAIL to your Gmail (gets is_admin=true in DB at startup).
3. `docker compose up --build` (API on :8000, Postgres).
4. `cd frontend && cp .env.example .env.local && npm i && npm run dev`
5. Stripe webhook: `stripe listen --forward-to localhost:8000/payments/webhook`

## Security notes
- Admin = `users.is_admin` checked in DB on every /admin call (403 otherwise). Only settable in the DB.
- Paid content is locked on the server (HTTP 402), not only hidden in the UI.
- Placement answers are sealed inside a signed token – never sent to the browser.
- Session = httpOnly cookie; set COOKIE_SECURE=true behind HTTPS.
