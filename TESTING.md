# Test strategy

Four layers, each answering a different question. Everything below is a
real artifact in this repo with real measured results — nothing
aspirational.

| Layer | Question it answers | Tooling | Size | Where it runs |
| --- | --- | --- | --- | --- |
| Backend unit + integration | Does every endpoint and service behave, including the failure paths? | pytest (+ pytest-cov) | 148 tests, 93% coverage (CI gate: 88%) | `backend/`, every push (CI `backend-tests`) |
| Frontend unit | Do the critical client pieces behave in isolation? | Vitest + React Testing Library (jsdom) | 16 tests | `frontend/src/**/*.test.*`, every push (CI `frontend-build`) |
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

## Frontend unit (Vitest)

```bash
cd frontend && npm test        # or: npm run test:watch
```

What's deliberately covered first (highest-risk client logic):

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

Config note: `vitest.config.ts` is separate from `vite.config.ts` on
purpose — the production build config stays untouched, and Vitest brings
its own Vite internally.

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
- **Environment honesty:** Playwright's browser download is blocked in
  the local development sandbox (network egress allowlist), so this
  suite is authored locally but *executed in CI*, where the `e2e` job
  installs Chromium and uploads traces on failure.

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

- Register-form E2E flow (user seeded via API instead).
- No visual-regression or screen-reader/axe automation yet (the v0.1.1
  contrast audit was static computation).
- Postgres path documented but untested; load numbers predate real model
  inference.
