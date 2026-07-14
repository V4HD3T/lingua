# Lingua — AI Translation and Language Learning Platform

**Version:** 0.0.3

A platform offering real-time translation and interactive language
learning for multilingual users. Built as part of a university graduation
project.

For the full architecture, technology rationale, and roadmap, see
**[ARCHITECTURE.md](./ARCHITECTURE.md)**.

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

- ✅ Backend: authentication, translation, courses/lessons/vocabulary, quizzes, progress/streak — 30 tests passing
- ✅ Frontend: a working interface for every flow (React + TypeScript)
- ✅ Speech recognition: voice input for translation + pronunciation practice (browser-based, no model download)
- ✅ Progress tracking: daily streak, per-course completion percentage (`/progress`)
- ⏳ Up next: the real NLLB model (needs to be set up locally), content expansion, end-to-end testing

(Full roadmap: `ARCHITECTURE.md` §6)
