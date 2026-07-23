# Test strategy

Four layers, each answering a different question. Everything below is a
real artifact in this repo with real measured results — nothing
aspirational.

| Layer | Question it answers | Tooling | Size | Where it runs |
| --- | --- | --- | --- | --- |
| Backend unit + integration | Does every endpoint and service behave, including the failure paths? | pytest (+ pytest-cov) | 267 tests, 93% coverage (CI gate: 88%) | `backend/`, every push (CI `backend-tests`) |
| Frontend unit + page | Do the client pieces behave in isolation, and does each page do the right thing with them? | Vitest + React Testing Library (jsdom) | 74 tests (23 unit, 51 page) | `frontend/src/**/*.test.*`, every push (CI `frontend-build`) |
| End-to-end | Do the seams hold — real browser, real backend, full journey? | Playwright (Chromium) | 1 journey spec | `frontend/e2e/`, every push (CI `e2e`) |
| Load | What happens under pressure — and does the rate limiter actually engage? | Locust | 4 scenarios, 2 modes | `backend/loadtest/`, run manually |

## Backend (pytest)

```bash
cd backend && pytest --cov=app --cov-report=term-missing
```

Highlights beyond plain endpoint coverage: the migration-drift test
(Alembic head must build exactly the SQLModel metadata), rate-limiter
behaviour including the `/health` exemption and `Retry-After` headers,
the served-set quiz-grading contract, Turkish case-folding, and the
translation cache's outage-degradation guarantees.

## Frontend unit + page (Vitest)

```bash
cd frontend && npm test        # or: npm run test:watch
```

### Unit — the highest-risk client logic, covered first

- **`api/client` token refresh** — transparent 401→refresh→retry,
  session teardown on refresh rejection, and the concurrency guarantee:
  N simultaneous 401s share **one** refresh call (the backend's refresh
  tokens are single-use; two racing rotations would trip reuse detection
  and kill the whole session).
- **Toast lifecycle** — success/error timing (4s/7s), `role="alert"`
  escalation, manual dismissal, provider guard.
- **Theme semantics** — the persist-only-on-explicit-toggle rule, and
  pickup of the pre-paint script's decision.
- **CopyButton** — including the blocked-clipboard failure path.
- **SentenceOrderInput** — order building, word return, duplicate words
  by position.

### Page — all 13 pages, one file each

Pages were the gap this layer closed (v0.1.14): until then their only
automated signal was that they compiled. Each page is rendered with the
router, auth context and toasts around it (`src/test/harness.tsx`) and its
API modules stubbed, so what's asserted is behaviour rather than markup —
what the page sends, and what it shows when the answer is bad.

What that pins down, page by page:

- **Translate** — the 400 ms debounce (one request per pause, not per
  keystroke) and the request-id guard that stops a slow answer from
  overwriting a newer one.
- **Quiz** — answers submitted keyed by question id together with the
  served-set `session_id`, both pre-submit guards (unanswered questions,
  missing session), and that "Try again" starts genuinely empty.
- **Review** — SM-2 quality values behind the Again/Good/Easy labels
  (1/3/5, not button positions), the card staying put when a rating fails
  to save, and the answer hidden again on the next card.
- **Progress** — the daily-goal bounds check that has to live in the page
  because the editor isn't a form (v0.1.7), and the verification notice
  appearing only for the unverified.
- **History** — the second page requested at the offset the list ends at,
  and appended rather than replacing.
- **Login / Register / Forgot / Reset / Verify** — the server's own
  message shown on failure with the form still usable; the verification
  page's single-use token spent exactly once under StrictMode (v0.1.12).
- **Courses / Course detail / Lesson detail** — "empty" told apart from
  "failed to load", and the lesson page asking about a quiz through the
  unauthenticated existence check, so browsing never mints a QuizSession.

Config notes:

- `vitest.config.ts` is separate from `vite.config.ts` on purpose — the
  production build config stays untouched, and Vitest brings its own Vite
  internally.
- `src/test/setup.ts` installs an in-memory `localStorage` when the
  runtime doesn't leave jsdom's in place. Node ≥ 24 defines a global
  `localStorage` that stays inert without `--localstorage-file`, and
  vitest's jsdom environment doesn't overwrite globals Node already
  defined — so on Node 24+ every `localStorage` call in the suite threw,
  while CI's Node 22 (Web Storage still behind a flag) stayed green.

## End-to-end (Playwright)

```bash
cd frontend && npx playwright install chromium   # once
npm run test:e2e
```

`playwright.config.ts` boots the **real** FastAPI backend (fresh
throwaway SQLite at `/tmp/lingua-e2e.db`, seeded content) and the Vite
dev server, then drives Chromium through the full learner journey:
login → live translation (with the saved-to-history notice as session
proof) → the seeded quiz answered to 100% via the session-graded flow →
history verification → dark-mode toggle.

Design choices worth knowing:

- The test user is **registered via the API**, not the form — keeps the
  spec independent of register-page copy, and email verification isn't
  required for login. The register form itself is a known E2E gap.
- Selectors ride the v0.1.1 accessibility work (labels, roles, fieldset
  legends as group names) — the a11y round paying for itself as
  testability.
- **Running it where the browser download is blocked:** point the suite
  at a Chromium already on disk with
  `E2E_CHROMIUM_PATH=/path/to/chrome npm run test:e2e`. CI leaves the
  variable unset and uses the browser Playwright manages, installing it
  in the `e2e` job and uploading traces on failure.

## Load (Locust)

```bash
cd backend
uvicorn app.main:app --port 8000                                  # terminal 1
locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 \
       --headless -u 15 -r 5 -t 30s                               # terminal 2
```

Single-IP load generation and per-IP rate limiting are fundamentally at
odds, so there are two documented modes — and both were actually run:

**Mode A — defaults (limiter verification).** 15 users, 20s: 227
requests, 152 rejected with 429 (67%). Server-side accounting: the first
76 requests served normally, then `/translate`'s 30/min budget engaged
(43 endpoint-level 429s), and as pressure continued the 120/min global
backstop took over (109 more). Rejections cost ~1–5 ms each — the
limiter holds under pressure and stays cheap while doing it. Latency
figures from this mode are meaningless by construction.

**Mode B — capacity (budgets raised via the v0.1.2 settings knobs
`API_RATE_LIMIT_PER_MINUTE` / `TRANSLATE_RATE_LIMIT_PER_MINUTE`).** 15
users, 30s: 349 requests, **0 failures**, aggregate ~11.6 req/s, p50
16 ms, p95 93 ms, max 238 ms. Baseline caveats: mock translation
service, SQLite, single process — these are floor numbers for the
architecture, not predictions for real NLLB inference.

All simulated users share one pre-created account (a `test_start`
listener): per-user registration would trip the auth limiters within
seconds of every run.

## Known gaps (kept honest)

- Register-form E2E flow (user seeded via API instead) — the form itself
  is covered at the page level, but not through a real browser.
- One journey spec only: it covers the critical path end to end, but
  error paths (bad credentials, expired session, failed submission) are
  still covered only at the unit, page and integration layers.
- Speech input/output paths (pronunciation practice, listening questions,
  read-aloud) aren't exercised: jsdom has neither of the Web Speech APIs,
  so the page tests always take the unsupported branch — the same one a
  Firefox user gets. The supported branch has no automated coverage at
  any layer.
- No visual-regression or screen-reader/axe automation yet (the v0.1.1
  contrast audit was static computation).
- Postgres path documented but untested; load numbers predate real model
  inference.
