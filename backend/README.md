# Backend — AI Translation and Language Learning Platform

**Version:** 0.0.5

A REST API written with FastAPI + SQLModel. Includes authentication,
real-time translation with automatic language detection, course/lesson/
vocabulary and quiz modules, spaced-repetition review, and progress/streak
tracking.

## What's new in 0.0.5

- `POST /translate` now also returns `confidence`, `alternatives`, and
  `idiom_warnings`. Real once NLLB is active (`translate_detailed()` on
  `NLLBTranslationService` uses genuine beam-search output); clearly
  documented mock placeholders until then.
- `GET /users/me/vocabulary-suggestions` — personalized suggestions from
  the user's own translation history.
- Idiom detection: small curated dictionary, `app/services/idiom_detection.py`.
- Confirmed empirically (via `curl`, `x-deny-reason: host_not_allowed`)
  that this environment still can't reach huggingface.co for real NLLB.
- 16 new tests (67 total).

## What's new in 0.0.4

- `POST /detect-language` — guesses the language of a piece of text,
  restricted to the app's 5 supported languages. Returns `is_reliable:
  false` for short/ambiguous input rather than a false-confident guess —
  see `app/services/language_detection.py` for why.
- `GET /users/me/review-queue` and `POST /vocabulary/{id}/review` — SM-2
  spaced repetition. New `VocabularyProgress` table.
- Text-to-speech is frontend-only (browser API), no backend change needed.
- 24 new tests (51 total).

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
- Health check: http://127.0.0.1:8000/health (also reports the running version)

On first startup, the database tables are created automatically and sample
data is added (5 languages, 1 course, 1 lesson, 2 vocabulary items, 1 quiz).

## Running the tests

```bash
pytest -v
```

67 tests; covers authentication, translation (anonymous + registered
user, confidence/alternatives, idiom warnings), language detection,
lesson/course flows, quizzes, spaced repetition, personalized vocabulary
suggestions, and progress/streak calculation. The tests use an isolated
in-memory SQLite database and don't touch the real `app.db` file.

## Switching to the real translation model

By default it runs with `USE_MOCK_TRANSLATION=true` — a mock translation
service is used that lets you test the API contract without downloading the
model. To switch to real transformer-based translation:

```bash
pip install transformers torch sentencepiece
```

In the `.env` file:
```
USE_MOCK_TRANSLATION=false
```

On the first request, the `facebook/nllb-200-distilled-600M` model is
downloaded automatically (~2.4 GB, requires an internet connection). This
single model supports 200+ languages on its own; add any languages you need
to the `NLLB_LANGUAGE_CODES` dictionary in
`app/services/translation_service.py`.

`NLLBTranslationService` implements two paths:
- `translate()` — the simple case, via HuggingFace's high-level
  `pipeline("translation", ...)` wrapper.
- `translate_detailed()` — the same, but also returns a real confidence
  score and genuine beam-search alternative translations. This needs the
  lower-level `AutoModelForSeq2SeqLM` / `AutoTokenizer` API rather than the
  simple pipeline wrapper. **I wrote this to the best of my knowledge of
  the `transformers` API, but could not execute it in this sandbox** (no
  network access to huggingface.co to fetch the model — verified with
  `curl`, returns `x-deny-reason: host_not_allowed`). Please sanity-check
  it against your installed `transformers` version once you have the real
  model running locally; the NLLB tokenizer's exact interface for
  language-code token IDs has changed across versions before.

## Translation confidence, alternatives, and idiom warnings

`POST /translate` also returns:
- `confidence` (0-1) and `alternatives` (list of strings) — genuine
  beam-search output once NLLB is active; **illustrative placeholder
  values from the mock service otherwise** (a text-length heuristic and a
  trivial formatting variant, respectively — see the docstring on
  `MockTranslationService` in `app/services/translation_service.py`).
- `idiom_warnings` — matches against a small, hand-curated dictionary per
  language (`app/services/idiom_detection.py`), not a trained classifier.
  Only catches the specific phrases listed there.

## Vocabulary suggestions from translation history

`GET /users/me/vocabulary-suggestions` looks at the user's own
`TranslationHistory`, counts which known vocabulary words show up
repeatedly, and suggests the ones they haven't started formally learning
yet (no `VocabularyProgress` record). Plain frequency counting, no ML —
see `app/services/personalized_suggestions.py`. This is the one feature
that actually connects the translate and learn modules to each other.

## Project structure

```
app/
  main.py            FastAPI entry point, router registration, sample data
  config.py          Settings read from environment variables
  database.py        SQLModel engine/session
  models.py          Database tables (User, Course, Quiz, VocabularyProgress, ...)
  schemas.py         API request/response schemas
  security.py        Password hashing + JWT
  services/
    translation_service.py   Mock + NLLB translation service abstraction
    language_detection.py    langid-based source language detection
    idiom_detection.py       Small curated idiom dictionary + matching
    personalized_suggestions.py  Vocabulary suggestions from translation history
    spaced_repetition.py     Pure SM-2 scheduling function
  routers/
    auth.py          /auth/register, /auth/login, /auth/me
    translate.py     /translate, /translate/history, /languages, /detect-language
    courses.py       /courses, /courses/{id}/lessons, /lessons/{id}, /lessons/{id}/vocabulary
    quizzes.py       /quizzes/{id}, /quizzes/{id}/submit, /lessons/{id}/quiz
    stats.py         /users/me/stats (streak, progress, overall statistics)
    review.py        /users/me/review-queue, /vocabulary/{id}/review (spaced repetition)
    suggestions.py   /users/me/vocabulary-suggestions (personalized, from translation history)
tests/               pytest test suite (67 tests)
```

## Authentication flow

1. `POST /auth/register` — register with username, email, password
2. `POST /auth/login` — log in with form-data (`username`, `password`), returns a JWT
3. Other protected endpoints are accessed with an `Authorization: Bearer <token>` header

The `/translate` endpoint deliberately supports both anonymous and
logged-in use: without a token, translation still works but isn't saved to
history; with a token, it is saved. This is a typical design for a "try it
without registering, see your history once you create an account" flow.
