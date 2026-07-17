# Lingua — AI Translation and Language Learning Platform

**Version:** 0.0.5

A platform offering real-time translation and interactive language
learning for multilingual users. Built as part of a university graduation
project.

For the full architecture, technology rationale, and roadmap, see
**[ARCHITECTURE.md](./ARCHITECTURE.md)**. For the complete version history,
see **[CHANGELOG.md](./CHANGELOG.md)**.

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

- ✅ Backend: auth, translation (+ confidence/alternatives/idiom warnings/language detection), courses/lessons/vocabulary, quizzes, progress/streak, spaced repetition, personalized suggestions — 67 tests passing
- ✅ Frontend: a working interface for every flow (React + TypeScript)
- ✅ Speech: voice input (translation + pronunciation practice) and voice output (translations + vocabulary), both browser-based, no model download
- ✅ Progress tracking: daily streak, per-course completion percentage (`/progress`)
- ✅ Spaced repetition: SM-2-scheduled vocabulary review (`/review`)
- ✅ AI/translation engine topic: complete except running the real NLLB model, which needs to happen on your own machine (this sandbox has no network access to huggingface.co)
- ⏳ Up next: content expansion, end-to-end testing, or a session to actually activate NLLB on your machine

(Full roadmap: `ARCHITECTURE.md` §6 · Full version history: `CHANGELOG.md`)
