# Lingua — AI Translation and Language Learning Platform

**Version:** 0.1.3

A platform offering real-time translation and interactive language
learning for multilingual users. Built as part of a university graduation
project.

For the full architecture, technology rationale, and roadmap, see
**[ARCHITECTURE.md](./ARCHITECTURE.md)**. For the complete version history,
see **[CHANGELOG.md](./CHANGELOG.md)**. For the security review, see
**[SECURITY.md](./SECURITY.md)**. For running and deploying it, see
**[DEPLOYMENT.md](./DEPLOYMENT.md)**. For the test strategy across all four
layers, see **[TESTING.md](./TESTING.md)**.

## Version history

One line per version; the full story (rationale, tradeoffs, bugs caught)
lives in [CHANGELOG.md](./CHANGELOG.md).

| Version | Summary |
| --- | --- |
| 0.0.1 | Backend skeleton: FastAPI + SQLModel, JWT auth, core translate/course/quiz endpoints (mock translation), seeded content. |
| 0.0.2 | Frontend: React + TypeScript (Vite) interface for every backend flow. |
| 0.0.3 | Browser speech recognition (dictation + pronunciation practice), streak & progress stats, lesson→quiz lookups. |
| 0.0.4 | Automatic language detection (with honest reliability gating), text-to-speech, SM-2 spaced repetition + `/review`. |
| 0.0.5 | Translation depth: confidence + alternatives, idiom warnings, personalized vocabulary suggestions, real-NLLB groundwork. |
| 0.0.6 | Pedagogy: four quiz types, adaptive difficulty, achievement badges, daily goals, grammar & cultural notes. |
| 0.0.7 | Security: refresh-token rotation, auth rate limiting, email verification & password reset, security headers, OWASP Top 10 audit, CI dependency scanning. |
| 0.0.8 | Test & CI infrastructure: pytest + coverage gate and frontend build on every push, app-wide rate limiting, paginated lists. |
| 0.0.9 | Alembic migrations (+ drift test), served-set quiz grading (`QuizSession`), admin content API; post-release: python-jose→PyJWT and Vite 8 — both dependency audits clean. |
| 0.1.0 | Ops: Docker + docker-compose (one command), Redis translation cache, CORS locked to the configured origin, deployment guide + Railway/Vercel configs. |
| 0.1.1 | UX: dark mode (token-level, no-flash), general toast system, copy-to-clipboard, accessibility audit — incl. fixing five measured WCAG failures the light theme had shipped with. |
| 0.1.2 | Test depth: first frontend unit tests (Vitest, 16), Playwright E2E journey in CI, Locust load testing with measured limiter verification, `TESTING.md`. |
| 0.1.3 | PWA (installable, offline shell, maskable icons, opt-in updates) and content as importable JSON packs — Turkish A1 + Spanish A2, tripling the catalogue. |

## Quick start

### Option A — one command (Docker)

```bash
docker compose up --build
```

→ Frontend: http://localhost:8080 · Backend + Swagger: http://localhost:8000/docs
(Swagger is development-only: `ENABLE_API_DOCS` defaults to off.)
(Environment variables and cloud deployment: `DEPLOYMENT.md`.)

### Option B — run directly (two terminals)

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

- ✅ Backend: auth (+ refresh tokens, email verification, password reset, rate limiting, daily goals), translation (+ confidence/alternatives/idiom warnings/language detection), courses/lessons (+ grammar/cultural notes), quizzes (4 types + adaptive difficulty), progress/streak, spaced repetition, personalized suggestions, achievement badges — 168 backend + 16 frontend tests passing
- ✅ Frontend: a working interface for every flow (React + TypeScript)
- ✅ Speech: voice input (translation + pronunciation practice) and voice output (translations + vocabulary + listening quiz questions), both browser-based, no model download
- ✅ Progress tracking: daily streak, daily review goal, per-course completion percentage, achievement badges (`/progress`)
- ✅ Spaced repetition: SM-2-scheduled vocabulary review (`/review`)
- ✅ Security: app-wide + per-endpoint rate limiting, refresh token rotation, security headers, CI dependency scanning, real OWASP Top 10 audit (`SECURITY.md`)
- ✅ Test & CI infrastructure: pytest + coverage gate and frontend type-check/build on every push (`.github/workflows/ci.yml`), paginated list endpoints
- ✅ Data layer & content ops: Alembic migrations (with a migration-drift test), served-set quiz grading via QuizSession, admin CRUD API for all course/quiz content (`scripts/make_admin.py` to promote)
- ✅ Ops & deploy: Docker + docker-compose (one command), Redis translation cache with graceful degradation, CORS locked to the configured frontend origin, deployment guide + Railway/Vercel configs (`DEPLOYMENT.md`)
- ✅ UX & accessibility: dark mode with pre-paint theme resolution, app-wide toast notifications, copy-to-clipboard, WCAG AA-audited palette (30/30 pairs, both themes), landmarks + skip link + labeled controls
- ✅ Test depth: four-layer strategy (`TESTING.md`) — backend pytest, frontend Vitest, Playwright E2E in CI, Locust load testing with measured rate-limiter verification
- ✅ PWA & content: installable app with offline shell and opt-in updates; course content as validated JSON packs (`scripts/import_content.py`) — Turkish A1 and Spanish A2 alongside the seeded course
- ✅ AI/translation engine topic: complete except running the real NLLB model, which needs to happen on your own machine (this sandbox has no network access to huggingface.co)
- ✅ Language learning/pedagogy topic: complete
- ✅ Security topic: complete
- ⏳ Up next: academic deliverables (ER/use-case/sequence diagrams, user guide) and activating the real NLLB model

(Full roadmap: `ARCHITECTURE.md` §6 · Full version history: `CHANGELOG.md` · Security review: `SECURITY.md`)
