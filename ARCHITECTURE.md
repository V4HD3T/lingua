# AI-Based Automatic Translation and Language Learning Platform

**Version:** 0.0.7

An integrated platform offering real-time translation and interactive
language learning (quizzes + vocabulary + speaking practice) for
multilingual users.

For the security review (OWASP Top 10 audit of this codebase), see
**[SECURITY.md](./SECURITY.md)**.

## 1. Scope

- Transformer-based translation engine (NLLB-200 — 200+ languages, single model)
- Automatic source-language detection
- Translation confidence scores, alternative translations, and idiom warnings
- Interactive quiz system: multiple choice, fill-in-the-blank, listening,
  sentence ordering — with difficulty that adapts to the learner
- Course → lesson → vocabulary hierarchy, with grammar/cultural notes
- Spaced repetition (SM-2) for vocabulary review
- Personalized vocabulary suggestions drawn from translation history
- Achievement badges and daily practice goals
- User accounts, session management (JWT + rotating refresh tokens),
  email verification, password reset, translation history
- Security: rate limiting, security response headers, CI dependency
  scanning, structured security event logging
- Progress tracking: daily streak, per-course completion percentage
- Browser-based speech recognition (dictation, pronunciation practice) and
  text-to-speech (hearing translations, vocabulary, and listening quiz questions)

## 2. Architecture

Four layers:

```
Client (Web)   →   API server (FastAPI)   →   ┬→ NLLB translation model
React + browser                               └→ Database
speech recognition                            (user, course, quiz, history)
```

- **Client**: React + TypeScript. Speech recognition runs client-side via
  the browser's built-in Web Speech API — no separate speech model, no
  extra load on the server, no additional download.
- **API server**: FastAPI. Serves authentication, translation, and
  course/lesson/quiz/progress endpoints over REST. Real-time translation
  works by having the client send a debounced (350-500ms) request while
  typing — no need for full WebSocket support, and it's sufficient for an
  MVP.
- **Translation engine**: `facebook/nllb-200-distilled-600M`. Since a
  single model covers 200+ languages, there's no need to manage a separate
  model per language pair (unlike the classic MarianMT approach).
- **Database**: SQLite in development; switching to PostgreSQL in
  production is a one-line change (`DATABASE_URL`), since the access layer
  is abstracted through SQLModel.

## 3. Technology choices and rationale

| Layer | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | Async support, automatic OpenAPI/Swagger docs, type safety (Pydantic) |
| ORM | SQLModel | Combines SQLAlchemy + Pydantic — the same class doubles as table and schema |
| Translation | HuggingFace `transformers` + NLLB-200 | Open source, free, directly satisfies the "transformer-based model" requirement, and is academically defensible (you can show how the model works instead of calling a black-box API) |
| Authentication | JWT (python-jose) + bcrypt | Stateless, works unchanged if a mobile client is added later |
| Frontend | React + TypeScript | Matches existing experience, large ecosystem |
| Speech recognition | Web Speech API (browser) | No server-side ASR model (Whisper, etc.) required; an optional server-side alternative can be added in a later phase |

## 4. Data model (summary)

- `User` — user account, native language, daily review goal
- `Language` — supported languages (code + name)
- `TranslationHistory` — the user's past translations
- `Course` → `Lesson` (+ grammar/cultural notes) → `VocabularyItem` — learning content hierarchy
- `Quiz` → `QuizQuestion` (type, difficulty), `QuizAttempt` — quiz questions and user attempts
- `VocabularyProgress` — one row per (user, word): SM-2 schedule (ease
  factor, interval, repetitions, next review date)
- `Achievement` — one row per (user, badge code) earned; badge catalogue
  itself lives in code, not the database
- `RefreshToken` — revocable, rotated session tokens (hash only, never
  the raw value)
- `AuthToken` — single-use email verification / password reset tokens
  (hash only, same reasoning)

See `backend/app/models.py` for the full field list.

## 5. Completed so far

**Phase 0 — Backend skeleton** ✅

- Register / login / JWT-protected endpoints (`/auth/*`)
- Real-time translation, anonymous + registered use, history saving (`/translate*`)
- Course → lesson → vocabulary endpoints (`/courses*`, `/lessons/*`)
- Quiz retrieval (both `/quizzes/{id}` and `/lessons/{id}/quiz`) + automatic scoring
- Clean abstraction between the mock translation service (for development
  without downloading a model) and the real NLLB service (one setting flips
  it on)

**Phase 2 — Frontend** ✅ (pulled ahead of its slot in the plan — putting a
real interface directly on top of the backend gave faster feedback)

- React + TypeScript, via Vite. Product name: **Lingua**.
- Pages: real-time translation (the signature page — debounced
  auto-translate + language swapping), login/register, course list → lesson
  list → vocabulary → quiz flow, translation history.
- A dedicated design token system (`src/styles/tokens.css`): a deep-navy +
  warm-amber palette, Space Grotesk/Inter type pairing — a deliberate
  identity rather than a templated look.
- `tsc -b` compiles clean under strict mode; backend and frontend were
  brought up together and verified end-to-end with live requests, CORS
  included.

**Phase 3 — Speech recognition** ✅ (pulled ahead of Phase 1/NLLB because
it's entirely client-side and could genuinely be verified end-to-end in
this environment)

- The browser's built-in Web Speech API (`useSpeechRecognition` hook) — no
  audio sent to a server, no extra model download.
- Microphone dictation on the translate page: spoken text is written into
  the source box and flows through the existing debounced translation
  pipeline unchanged.
- Pronunciation practice on the lesson page: a mic button next to each
  vocabulary word compares what's said against the word and gives instant
  feedback.
- Required one small backend addition: `GET /lessons/{id}` now also returns
  the language code of the lesson's parent course (needed to know which
  language to listen in).
- The mic button hides itself automatically in browsers that don't support
  the API (e.g. Firefox); the app keeps working fine with the keyboard.

**Phase 4 — Progress tracking / streak system** ✅

- `GET /users/me/stats`: daily streak, longest streak, total
  translation/quiz counts, average quiz score, per-course completion
  percentage.
- The streak is **not** stored in a separate counter table — it's computed
  directly from the dates on `TranslationHistory` and `QuizAttempt`
  records, so it can never drift out of sync with real activity.
- A lesson counts as "completed" once its quiz has been attempted at least
  once.
- The streak calculation (the trickiest part — today/yesterday/gap
  handling) is covered by 6 dedicated pure unit tests.
- Frontend: the `/progress` page — a streak card with a flame icon, quick
  stat tiles, and per-course progress bars. "Progress" link in the NavBar
  (visible when logged in).

Backend: **67 tests passing**. See `backend/README.md` and
`frontend/README.md` for setup and run instructions.

**v0.0.4 — Automatic language detection, text-to-speech, spaced
repetition** ✅ (from here on, new work is tracked by version rather than
by the original phase numbers below — see `CHANGELOG.md` for the itemized
list of every version's changes)

- `POST /detect-language`, restricted to the app's 5 supported languages,
  gated by a length + confidence heuristic after empirically finding that
  short greetings are genuinely unreliable with a lightweight offline
  model. Opt-in on the frontend ("Detect language" dropdown option) —
  never silently overrides a manual choice.
- `useSpeechSynthesis` hook (browser `SpeechSynthesis` API): speaker
  buttons on the translate page and next to each vocabulary word, so
  learners hear a word before the mic asks them to say it.
- Real SM-2 spaced repetition: `VocabularyProgress` table, `GET
  /users/me/review-queue`, `POST /vocabulary/{id}/review`, and a
  flashcard-style `/review` page (reveal → rate Again/Good/Easy).
- 24 new tests (51 total), all three features verified live end-to-end.

**v0.0.5 — AI / translation engine, remaining items** ✅ (topic complete
except running real NLLB, which needs your own machine)

- `translate_detailed()` added to `TranslationService`: real
  confidence + beam-search alternatives on `NLLBTranslationService`
  (written, not executable here — see below); clearly-labeled
  illustrative placeholders on `MockTranslationService`.
- Idiom warnings: small curated dictionary per language, substring
  matching on stable (non-conjugating) phrase stems.
- `GET /users/me/vocabulary-suggestions`: frequency-counts the user's own
  translation history against the vocabulary catalogue — the one feature
  that actually connects translate and learn.
- Re-verified empirically that this sandbox can't reach huggingface.co
  (`curl` → `x-deny-reason: host_not_allowed`); everything else needed for
  real NLLB is written and documented, ready for a session on your
  machine.
- 16 new tests (67 total) — including two real bugs the tests themselves
  caught and fixed before this was called done (details in
  `CHANGELOG.md`).

**v0.0.6 — Language learning / pedagogy** ✅ (topic complete)

- Quiz questions gained a `question_type`: multiple choice (existing),
  fill-in-the-blank, listening (reuses the v0.0.4 text-to-speech hook),
  and sentence ordering (new drag-free click-to-build UI). `matching` was
  considered and deliberately deferred — it wants a proper pairs table,
  not a hack on the existing flat schema.
- Adaptive difficulty: `difficulty` (1-3) on each question; selection now
  factors in the learner's recent average score. Caught and fixed a real
  design bug while building this — quiz scoring used to grade against
  every question in the quiz, which would have unfairly penalized
  adaptive selection showing only a subset; now grades only what was
  actually submitted.
- Achievement badges: 8-badge catalogue, checked after translate/quiz/
  review actions, shown as a toast when newly earned and listed on
  `/progress`.
- Daily review goal, editable, tracked against today's review count.
- Grammar/cultural notes on lessons.
- "Flashcard mode" needed no new work — already delivered in v0.0.4 as
  the `/review` page.
- Refactored streak computation into its own service module (now used
  from two places: stats display and streak-badge checking).
- 18 new tests (85 total).

**v0.0.7 — Security** ✅ (topic complete)

- Refresh tokens with rotation + reuse detection (`RefreshToken` table);
  access tokens shortened from 24h to 30 minutes now that sessions don't
  depend on the access token itself being long-lived.
- Rate limiting on login/register/password-reset (in-memory, documented
  as not shared across multiple worker processes).
- Full email verification + password reset flows behind a mock/real
  `EmailService` abstraction (no SMTP credentials in this sandbox).
- Security response headers, structured security event logging, CI
  dependency scanning (`pip-audit` + `npm audit`).
- A genuine OWASP Top 10 audit (`SECURITY.md`) against this actual
  codebase — including a transitive `ecdsa` CVE finding I verified
  empirically is not reachable given this app's HS256-only JWT usage,
  and honest pre-production requirements (restrict CORS, set a real
  `SECRET_KEY`) rather than a checklist of green checkmarks.
- Caught and fixed two real bugs: a repeat of v0.0.6's `is None` vs.
  `.is_(None)` SQLAlchemy mistake, and a SQLite-returns-naive-datetimes
  bug in token expiry comparisons.
- 21 new tests (106 total).

## 6. Roadmap

| Phase | Duration | Content |
|---|---|---|
| 0 | ✅ Done | Architecture design, backend skeleton, test suite |
| 2 | ✅ Done | Frontend: translation UI, course/lesson flow, quiz UI |
| 3 | ✅ Done | Speech recognition / pronunciation practice via the Web Speech API |
| 4 | ✅ Done | Progress tracking, streak system |
| — | ✅ Done (v0.0.4) | Automatic language detection, text-to-speech, spaced repetition |
| — | ✅ Done (v0.0.5) | Translation confidence/alternatives, idiom warnings, personalized vocabulary suggestions |
| — | ✅ Done (v0.0.6) | Quiz types, adaptive difficulty, achievement badges, daily goals, lesson notes |
| — | ✅ Done (v0.0.7) | Refresh tokens, rate limiting, email flows, security headers, CI scanning, OWASP audit |
| — | ✅ Done (v0.0.8) | CI test workflow + coverage gate, app-wide rate limiting, paginated list endpoints |
| — | ✅ Done (v0.0.9) | Alembic migrations + drift test, QuizSession served-set grading, admin content API |
| — | ✅ Done (v0.1.0) | Docker + compose, Redis translation cache, CORS allowlist, deployment guide |
| — | ✅ Done (v0.1.1) | Dark mode, toast system, clipboard, WCAG AA contrast audit + a11y fixes |
| — | ✅ Done (v0.1.2) | Vitest frontend units, Playwright E2E in CI, Locust load tests, TESTING.md |
| 1 | pending — your machine | Real NLLB model integration (confirmed empirically: no network access to huggingface.co in this environment) |
| 5 | pending | End-to-end testing, usability evaluation, bug fixing |
| 6 | pending | Project report, documentation, defense presentation |

Three full topics from the working list ("AI / translation engine",
"Dil öğrenme / pedagoji", and "Güvenlik") are now done except real NLLB,
which is blocked on this environment's network access rather than on
remaining design or implementation work.

## 7. Next step

Content expansion, frontend testing, the end-to-end testing/usability
phase, or a session on your own machine to actually activate real NLLB —
which one?
