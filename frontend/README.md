# Frontend — Lingua

**Version:** 0.0.5

A single-page app built with Vite + React + TypeScript. Consumes the
backend's authentication, translation (with language detection), course/
lesson/vocabulary, quiz, spaced-repetition review, and progress endpoints.

## What's new in 0.0.5

- Translate page now shows a **confidence badge** and any **alternative
  translations** next to the output, plus an **idiom warning** box under
  the source text when a known idiomatic phrase is detected.
- `/progress` gained a **"Picked up from your translations"** section:
  words you've translated repeatedly that you haven't started formally
  learning yet, linking straight to the relevant lesson.

## What's new in 0.0.4

- **"Detect language"** option in the translate page's source dropdown —
  opt-in, shows the guess plus a "(not sure — check this)" flag when
  confidence is low, never silently overrides a manual choice.
- **Speaker buttons** (`useSpeechSynthesis` hook, `SpeakerButton`
  component) on the translate page and next to each vocabulary word.
- **`/review`** — a new flashcard-style spaced-repetition page.

## Setup

```bash
cd frontend
npm install
cp .env.example .env
```

`VITE_API_URL` in `.env` points to where the backend is running (default:
`http://localhost:8000`).

## Running

The backend needs to already be running in a separate terminal (see
`../backend/README.md`). Then:

```bash
npm run dev
```

The app opens at http://localhost:5173.

## Production build

```bash
npm run build     # type-checking + build into dist/
npm run preview   # serves the built version locally
```

## Site map

| Path | Description |
|---|---|
| `/` | Real-time translation, with optional language detection (no login required) |
| `/login`, `/register` | Authentication |
| `/courses` | Course list |
| `/courses/:courseId` | Course detail + lesson list |
| `/lessons/:lessonId` | Vocabulary (listen + pronunciation practice) + entry point to the quiz |
| `/lessons/:lessonId/quiz` | Taking the quiz (requires login) |
| `/review` | Spaced-repetition flashcard review (requires login) |
| `/progress` | Streak, course progress, overall stats (requires login) |
| `/history` | Translation history (requires login) |

## Architecture notes

- **`src/api/`** — a thin client layer that mirrors the backend endpoints.
  Every request goes through `api/client.ts` (token attachment and error
  normalization live in one place).
- **`src/context/AuthContext.tsx`** — keeps the JWT in `localStorage` and
  verifies it against `/auth/me` on load. Since this is a real standalone
  project running in your own browser (not a Claude.ai artifact preview),
  using `localStorage` here is safe.
- **Design tokens** live in one place, `src/styles/tokens.css` (color,
  typography, spacing scale) — use those variables when adding new
  components.
- Every page ships with its own CSS Modules file (`Page.module.css`) — no
  risk of global class name collisions.

## Speech: input and output

**Input (speech-to-text)** — the translate page (`/`) has a microphone icon
inside the source text box, and the lesson page (`/lessons/:id`) has one
next to each vocabulary word. Both go through
`src/hooks/useSpeechRecognition.ts`, wrapping the browser's built-in
`SpeechRecognition` / `webkitSpeechRecognition` API.

**Output (text-to-speech)** — a speaker icon next to the translation
output and next to each vocabulary word, via
`src/hooks/useSpeechSynthesis.ts`, wrapping the browser's built-in
`SpeechSynthesis` API. Broader browser support than speech-to-text
(Firefox has it too).

For both:
- Nothing is sent to any server, and no extra model is downloaded.
- Buttons hide themselves automatically in unsupported browsers; the app
  keeps working fine with the keyboard/eyes alone.
- Requires permission on `localhost`; production requires HTTPS (a browser
  restriction, not an app one).

The pronunciation practice on the lesson page normalizes the spoken word
(lowercase + trimmed) and compares it to the expected word exactly; this
is a simple, transparent check that could later be improved with fuzzy
matching (e.g. Levenshtein distance) if desired.

## Spaced repetition

`/review` is a flashcard loop: see the word (with a speaker button to hear
it), reveal the translation, rate yourself Again/Good/Easy. That rating
drives a real SM-2 scheduling algorithm on the backend — see
`backend/app/services/spaced_repetition.py`.

## Known warning

`npm audit` reports a moderate-severity advisory about the `esbuild`
dependency in Vite's dev server (only during `npm run dev`, doesn't affect
the production build). Fixing it requires a breaking upgrade to Vite 8;
deliberately deferred for now. Details:
https://github.com/advisories/GHSA-67mh-4wv8-2f99
