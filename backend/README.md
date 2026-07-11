# Backend — AI Translation and Language Learning Platform

**Version:** 0.0.1

A REST API written with FastAPI + SQLModel. Includes authentication,
real-time translation, and course/lesson/vocabulary and quiz modules.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Running

```bash
uvicorn app.main:app --reload
```

Once the server is up:
- API: http://127.0.0.1:8000
- Automatic Swagger documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

On first startup, the database tables are created automatically and
sample data is added (5 languages, 1 course, 1 lesson, 2 vocabulary
items, 1 quiz).

## Running the tests

```bash
pytest -v
```

12 tests; covers authentication, translation (anonymous + registered
user), and the full lesson/course and quiz flows. The tests use an
isolated in-memory SQLite database and don't touch the real `app.db`
file.

## Switching to the real translation model

By default it runs with `USE_MOCK_TRANSLATION=true` — a mock translation
service is used that lets you test the API contract without downloading
the model. To switch to real transformer-based translation:

```bash
pip install transformers torch sentencepiece
```

In the `.env` file:
```
USE_MOCK_TRANSLATION=false
```

On the first request, the `facebook/nllb-200-distilled-600M` model is
downloaded automatically (~2.4 GB, requires an internet connection).
This single model supports 200+ languages on its own; you can add any
languages you need to the `NLLB_LANGUAGE_CODES` dictionary in
`app/services/translation_service.py`.

## Project structure

```
app/
  main.py            FastAPI entry point, router registration, sample data
  config.py          Settings read from environment variables
  database.py        SQLModel engine/session
  models.py          Database tables (User, Course, Quiz, ...)
  schemas.py         API request/response schemas
  security.py        Password hashing + JWT
  services/
    translation_service.py   Mock + NLLB translation service abstraction
  routers/
    auth.py          /auth/register, /auth/login, /auth/me
    translate.py     /translate, /translate/history, /languages
    courses.py       /courses, /courses/{id}/lessons, /lessons/{id}/vocabulary
    quizzes.py       /quizzes/{id}, /quizzes/{id}/submit
tests/               pytest test suite (12 tests)
```

## Authentication flow

1. `POST /auth/register` — register with username, email, password
2. `POST /auth/login` — log in with form-data (`username`, `password`), returns a JWT
3. Other protected endpoints are accessed with an `Authorization: Bearer <token>` header

The `/translate` endpoint deliberately supports both anonymous and
logged-in use: without a token, translation still works but isn't
saved to history; with a token, it is saved. This is a typical design
for a "try it without registering, see your history once you create an
account" flow.
