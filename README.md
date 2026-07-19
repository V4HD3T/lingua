# Lingua — AI Translation and Language Learning Platform

**Version:** 0.0.7

A platform offering real-time translation and interactive language
learning for multilingual users. Built as part of a university graduation
project.

For the full architecture, technology rationale, and roadmap, see
**[ARCHITECTURE.md](./ARCHITECTURE.md)**. For the complete version history,
see **[CHANGELOG.md](./CHANGELOG.md)**. For the security review, see
**[SECURITY.md](./SECURITY.md)**.

## What's new in 0.0.7

Completes the "Güvenlik" topic:

- **Refresh tokens + revocation** — short-lived (30 min) access tokens,
  server-side-revocable refresh tokens with rotation. A replayed/stolen
  refresh token now kills every session for that user, not just itself.
- **Rate limiting** on login, registration, and password-reset requests.
- **Email verification + password reset** — full flows, with a mock email
  service (no real SMTP credentials in this sandbox, but the architecture
  and all logic is real and tested).
- **Security headers** (CSP, HSTS, X-Frame-Options, and more) on every response.
- **CI dependency scanning** — `pip-audit` + `npm audit` on every push and weekly.
- **A real OWASP Top 10 audit** (`SECURITY.md`) — genuine findings, not a
  checklist: a CORS wildcard that must be fixed before production, a weak
  default secret key (now warned about at startup), and a transitive
  dependency CVE that I verified is actually unreachable given how this
  app uses JWTs.
- Backend: 106/106 tests passing (21 new this version).

## What's new in 0.0.6

Completes the "Dil öğrenme / pedagoji" topic:

- **New quiz types**: fill-in-the-blank, listening (uses text-to-speech),
  sentence ordering — on top of the existing multiple choice.
- **Adaptive difficulty**: quiz questions now skew easier or harder based
  on your recent average score.
- **Achievement badges**: 8 badges (first translation, quiz milestones,
  streak milestones, and more), shown as a toast when earned and listed
  on `/progress`.
- **Daily goal**: set a "words to review today" target, tracked with a
  progress bar on `/progress`.
- **Lesson content**: grammar and cultural notes on the lesson page.
- Flashcard mode needed no new work — already covered by the `/review`
  page from v0.0.4.
- Backend: 85/85 tests passing (18 new this version).

## What's new in 0.0.5

Completes the "AI / translation engine" topic:

- **Confidence score + alternative translations** on every `/translate`
  response. Real once NLLB is active; clearly-labeled mock placeholders
  until then.
- **Idiom warnings** — flags phrases like "piece of cake" or "en las
  nubes" as non-literal, from a small curated dictionary (5 languages).
- **Personalized vocabulary suggestions** — words you keep translating
  that you haven't formally started learning yet, shown on `/progress`.
  The one feature that actually connects translation and learning.
- **Real NLLB integration** — confirmed (empirically, via `curl`) this
  sandbox still can't reach huggingface.co. Everything buildable without
  actually running the model is done and documented; running it for real
  is queued for your own machine.
- Backend: 67/67 tests passing (16 new this version) — including two real
  bugs the new tests caught and fixed before shipping.

Full details in `CHANGELOG.md`.

## Quick start

You'll need two terminals — one for the backend, one for the frontend.

**Terminal 1 — Backend**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```
→ http://localhost:8000 (Swagger: http://localhost:8000/docs)

**Terminal 2 — Frontend**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
→ http://localhost:5173

See `backend/README.md` and `frontend/README.md` for detailed instructions
and architecture notes.

## Status

- ✅ Backend: auth (+ refresh tokens, email verification, password reset, rate limiting, daily goals), translation (+ confidence/alternatives/idiom warnings/language detection), courses/lessons (+ grammar/cultural notes), quizzes (4 types + adaptive difficulty), progress/streak, spaced repetition, personalized suggestions, achievement badges — 106 tests passing
- ✅ Frontend: a working interface for every flow (React + TypeScript)
- ✅ Speech: voice input (translation + pronunciation practice) and voice output (translations + vocabulary + listening quiz questions), both browser-based, no model download
- ✅ Progress tracking: daily streak, daily review goal, per-course completion percentage, achievement badges (`/progress`)
- ✅ Spaced repetition: SM-2-scheduled vocabulary review (`/review`)
- ✅ Security: rate limiting, refresh token rotation, security headers, CI dependency scanning, real OWASP Top 10 audit (`SECURITY.md`)
- ✅ AI/translation engine topic: complete except running the real NLLB model, which needs to happen on your own machine (this sandbox has no network access to huggingface.co)
- ✅ Language learning/pedagogy topic: complete
- ✅ Security topic: complete
- ⏳ Up next: content expansion, end-to-end testing, or a session to actually activate NLLB on your machine

(Full roadmap: `ARCHITECTURE.md` §6 · Full version history: `CHANGELOG.md` · Security review: `SECURITY.md`)
