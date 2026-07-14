# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/), versioned as
`MAJOR.MINOR.PATCH` — a new PATCH version for each feature/topic we
complete, until the project is stable enough for a 1.0.0.

Versions 0.0.1 through 0.0.3 were originally built and documented in
Turkish, then each given an English mirror at the same version number
(0.0.1 self-translated and reviewed together, 0.0.2 and 0.0.3 translated
directly). New features from here on start at 0.0.4.

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
