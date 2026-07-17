# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/), versioned as
`MAJOR.MINOR.PATCH` — a new PATCH version for each feature/topic we
complete, until the project is stable enough for a 1.0.0.

Versions 0.0.1 through 0.0.3 were originally built and documented in
Turkish, then each given an English mirror at the same version number
(0.0.1 self-translated and reviewed together, 0.0.2 and 0.0.3 translated
directly). New features starting from 0.0.4 are English-only going
forward, one PATCH version per completed feature/topic.

## [0.0.5] — AI / translation engine, remaining items

Completes the "AI / translation engine" topic. Four items:

- **Translation confidence + alternative translations** (`POST
  /translate` now also returns `confidence` and `alternatives`):
  - `TranslationService` gained a `translate_detailed()` method.
    `NLLBTranslationService`'s version is written against the real
    beam-search generation API (`num_return_sequences`,
    `output_scores=True`) for genuine alternatives and a real confidence
    score — **written but not executable in this sandbox** (no network
    access to huggingface.co; confirmed again with `curl`, which returns
    `x-deny-reason: host_not_allowed`), so it needs a quick sanity check
    against your installed `transformers` version once it's runnable.
  - `MockTranslationService`'s version returns clearly-documented
    illustrative placeholders (a text-length heuristic, a trivial
    formatting variant) — the frontend badge says "confidence" but its
    tooltip is upfront that this is a mock value.
- **Contextual / idiomatic-phrase warnings** (`idiom_warnings` field on
  the same `/translate` response):
  - A small hand-curated dictionary per language (5 languages, ~4-5
    idioms each), matched by case-insensitive substring search —
    deliberately simple and fully deterministic, not a trained classifier.
  - Dictionary entries use the idiom's stable, non-conjugating core (e.g.
    Spanish "en las nubes" rather than "estar en las nubes") so they still
    match conjugated real-world usage.
- **Personalized vocabulary suggestions** (`GET
  /users/me/vocabulary-suggestions`):
  - Counts words from the user's own `TranslationHistory` that also
    appear in the app's vocabulary catalogue, excluding anything they've
    already started reviewing. The one feature that actually connects the
    translate and learn modules rather than leaving them side by side.
  - Caught and fixed a real bug during testing: the mock translation
    service echoes the source text into its fake "translation," which was
    silently double-counting word frequency. Fixed by counting per-record
    presence (a set per translation, unioned into the counter) instead of
    raw token occurrences — also just a more correct design regardless of
    mock vs. real translation.
  - Shown on the `/progress` page as "Picked up from your translations."
- **Real NLLB integration**: confirmed (again, empirically, not from
  memory) that this sandbox cannot reach huggingface.co. Everything that
  *can* be done without actually running the model is done: the real
  service class, its detailed-translation method, and setup docs are all
  in place and ready to switch on (`USE_MOCK_TRANSLATION=false` +
  `pip install transformers torch sentencepiece`) — actually exercising it
  is queued for a session on your own machine.
- 16 new tests (67 total). Two genuine bugs were caught and fixed by the
  new tests themselves before this was called done (an idiom dictionary
  entry that couldn't match conjugated Turkish text, and the frequency
  double-counting bug above) — both described in more detail in the
  relevant test files.

## [0.0.4] — Automatic language detection, text-to-speech, spaced repetition

- **Automatic language detection** (`POST /detect-language`, `langid` library):
  - The translate page's source dropdown now offers "Detect language" as
    an explicit, opt-in choice — it never silently overrides a language
    you picked yourself.
  - Tested this empirically before trusting it: short greetings ("Bonjour",
    "Merhaba") are genuinely unreliable with a lightweight offline model —
    in testing, some were confidently misclassified. Detection is
    restricted to the app's 5 supported languages (cuts down on unrelated
    false matches) and is only ever applied when the text is at least 12
    characters *and* the model's confidence is at least 0.6; otherwise the
    UI shows the guess but flags it "(not sure — check this)".
  - 8 new backend tests, using sentences individually verified against the
    real classifier rather than assumed.
- **Text-to-speech** (`useSpeechSynthesis` hook, browser `SpeechSynthesis`
  API — no backend involved):
  - A speaker button next to the translation output reads it aloud.
  - A speaker button next to each vocabulary word on the lesson page, so
    you hear a word correctly *before* the existing microphone practice
    asks you to say it.
  - No audio sent anywhere, no model downloaded — same approach as the
    existing speech-to-text feature.
- **Spaced repetition / SM-2 algorithm** (`GET /users/me/review-queue`,
  `POST /vocabulary/{id}/review`, new `/review` page):
  - Real SM-2 scheduling (ease factor, interval, repetitions) — the same
    algorithm behind SuperMemo and Anki — implemented as a pure, unit-
    tested function (13 new tests, including a check that the ease factor
    can never drop below the algorithm's 1.3 floor even after 20 straight
    failures).
  - Flashcard-style review flow: see the word, reveal the answer, rate
    yourself Again/Good/Easy; the next review date is computed from that
    rating.
  - New `VocabularyProgress` table, one row per (user, word), so every
    learner gets their own independent schedule for the same word.
- Backend: 51/51 tests passing. Frontend: clean `tsc -b` strict build.
  All three features verified live end-to-end (not just unit-tested).

## [0.0.3] — Speech recognition, progress tracking, English translation

- Added browser-based speech recognition (Web Speech API): microphone
  dictation on the translate page, pronunciation practice on the lesson
  page. Audio never leaves the browser, no extra model download.
- Added `GET /lessons/{id}` (returns the lesson's course language code)
  and `GET /lessons/{id}/quiz`.
- Added `GET /users/me/stats`: daily streak (computed from activity dates,
  not stored, so it can't drift out of sync), longest streak, total
  translations/quiz attempts, average quiz score, per-course completion
  percentage.
- Added the `/progress` frontend page.
- Backend test suite grew to 30 tests (6 of them dedicated streak-logic
  unit tests).
- Translated all backend and frontend code (comments, docstrings, error
  messages, UI text) and all docs (`README.md` ×3, `ARCHITECTURE.md`) from
  Turkish to English.
- Switched the demo seed data from an English-for-Turkish-speakers course
  to a **Spanish for Beginners** course (`hola` → `hello`), so the demo is
  fully legible to an English-reading audience — code, docs, and content
  all consistent. Default `native_language` changed from `"tr"` to `"en"`.
- 30/30 backend tests and a clean `tsc -b` strict build confirmed after
  translation.

## [0.0.2] — Frontend

- Added the React + TypeScript frontend (Vite), product name **Lingua**.
- Pages: real-time translation, login/register, course → lesson →
  vocabulary → quiz flow, translation history.
- Custom design token system (color palette, typography, spacing).
- Backend: added `GET /lessons/{id}/quiz` so the frontend can jump from a
  lesson straight to its quiz.
- Translated to English at the same version number.

## [0.0.1] — Backend skeleton

- FastAPI + SQLModel backend: authentication (JWT), real-time translation
  (mock service + real NLLB service abstraction), courses/lessons/
  vocabulary, quizzes with automatic scoring.
- 12-test pytest suite.
- Initial `ARCHITECTURE.md` and setup docs.
- Translated to English at the same version number.
