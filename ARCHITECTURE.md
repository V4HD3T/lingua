# AI-Based Automatic Translation and Language Learning Platform

An integrated platform offering real-time translation and interactive
language learning (quizzes + vocabulary + speaking practice) for
multilingual users.

## 1. Scope

- Transformer-based translation engine (NLLB-200 — 200+ languages, single model)
- Interactive quiz system (multiple choice, automatic scoring)
- Course → lesson → vocabulary hierarchy
- User accounts, session management (JWT), translation history
- (Next phase) Browser-based speech recognition for pronunciation practice

## 2. Architecture

Four layers:

```
Client (Web)  →  API server (FastAPI)  →  ┬→ NLLB translation model
React + browser                           └→ Database
speech recognition                        (user, course, quiz, history)
```

- **Client**: React + TypeScript. Speech recognition is done client-side
  with the browser's built-in Web Speech API — this avoids putting extra
  load on the server with a separate speech model and requires no
  additional model download.
- **API server**: FastAPI. Serves authentication, translation, and
  course/lesson/quiz endpoints as REST. Real-time translation is achieved
  by having the client send debounced (350-500ms) requests while
  typing — this doesn't require full WebSocket support and is sufficient
  for an MVP.
- **Translation engine**: `facebook/nllb-200-distilled-600M`. Since a
  single model supports 200+ languages, you don't need to manage a
  separate model for every language pair (unlike the classic MarianMT
  approach).
- **Database**: SQLite in development, can be switched to PostgreSQL in
  production with a one-line change (`DATABASE_URL`), because the access
  layer is abstracted through SQLModel.

## 3. Technology choices and rationale

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python + FastAPI | Async support, automatic OpenAPI/Swagger documentation, type safety (Pydantic) |
| ORM | SQLModel | Combines SQLAlchemy + Pydantic, the same class serves as both table and schema |
| Translation | HuggingFace `transformers` + NLLB-200 | Open source, free, directly satisfies the "transformer-based model" requirement, academically defensible (you need to show how the model works rather than calling a black-box API) |
| Authentication | JWT (python-jose) + bcrypt | Stateless, works unchanged if you move to a mobile client |
| Frontend | React + TypeScript | Matches your existing experience, broad ecosystem |
| Speech recognition | Web Speech API (browser) | Requires no server-side ASR model (Whisper, etc.); an optional server-side alternative can be added in a later phase |

## 4. Data model (summary)

- `User` — user account, native language
- `Language` — supported languages (code + name)
- `TranslationHistory` — the user's past translations
- `Course` → `Lesson` → `VocabularyItem` — learning content hierarchy
- `Quiz` → `QuizQuestion`, `QuizAttempt` — quiz questions and user attempts

See `backend/app/models.py` for the full field list.

## 5. Completed so far (Phase 0)

The backend skeleton is up and running, and tested:

- ✅ Register / login / JWT-protected endpoints (`/auth/*`)
- ✅ Real-time translation, anonymous + registered use, history saving (`/translate*`)
- ✅ Course → lesson → vocabulary endpoints (`/courses*`, `/lessons/*`)
- ✅ Quiz retrieval + automatic scoring (`/quizzes/*`)
- ✅ 12-test pytest suite, all passing
- ✅ Clean abstraction between the mock translation service (for
  development without downloading the model) and the real NLLB service
  (activated with a one-line setting change)

See `backend/README.md` for setup and run instructions.

## 6. Roadmap (~6 months to graduation)

| Phase | Duration | Content |
|---|---|---|
| 0 | ✅ Complete | Architecture design, backend skeleton, test suite |
| 1 | 2-3 weeks | Real NLLB model integration, content expansion (more courses/lessons) |
| 2 | 3-4 weeks | Frontend: translation UI, course/lesson flow, quiz UI |
| 3 | 2-3 weeks | Speech recognition / pronunciation practice with the Web Speech API |
| 4 | 2 weeks | Progress tracking, streak system, UX improvements |
| 5 | 2-3 weeks | End-to-end testing, usability evaluation, bug fixing |
| 6 | 2 weeks | Project report, documentation, defense presentation |

Total ~15-19 weeks; leaves a comfortable buffer within the 6-month window.

## 7. Next step

When you're ready to move to Phase 1: real integration of the NLLB
model, expanding the course content, or starting directly on the
frontend (React + TS scaffold) — which would you like to see first?
