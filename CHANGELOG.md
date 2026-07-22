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

## [0.1.7] — Security log integrity

Fourth finding from the v0.1.3 security review, and the first that isn't
about the rate limiter. The previous three protected the login endpoint;
this one protects the record of what happened at it.

### Fixed

- **The security log could be forged by anyone who could reach
  `/auth/login`.** Field values went into the line verbatim, and login
  logs the username it was handed — a value `OAuth2PasswordRequestForm`
  subjects to no validation whatsoever: no length, no charset, no
  content rules. A username containing a newline emitted a *second* log
  line, written by the caller. Demonstrated concretely against the
  pre-fix code: one `log_event("login_failed", username=…)` call produced
  two lines, the second a backdated, correctly-formatted
  `login_succeeded user_id=1 username=admin` — nothing about it
  distinguishable from a genuine entry.

  This is not a formatting nuisance. SECURITY.md's entire A09 answer is
  "the events, in a consistent, greppable shape", and every reader of
  these logs — a human grepping after an incident, or the aggregator
  that would eventually alert on them — assumes one event per line.
  Someone who can break that assumption can make the audit trail say the
  opposite of what happened.

  `log_event` now escapes values through `repr()`, which is the standard
  reversible answer: newlines become `\n`, and control characters and
  non-printables — terminal escape sequences that repaint the screen of
  whoever `cat`s the log, bidirectional overrides that make a value
  render as something other than what it is — become numeric escapes.
  Values are also length-capped at 200 characters, because the login form
  imposes no limit and one request could otherwise write a megabyte of
  log.

  Values that need no escaping are still written bare, so `user_id=5` and
  `ip=1.2.3.4` read exactly as before and existing greps keep working —
  there's a test pinning that specifically, including that non-ASCII
  usernames (Turkish, Greek) stay unquoted rather than becoming
  unreadable escapes.

  Fixed centrally in `log_event` rather than at the call sites, so it
  covers all four places that log user-controlled data today and anything
  added later. One of those four was introduced by v0.1.6 itself: the
  login rate-limit key is `"<address>\x00<username>"`, so the username
  reaches the log through `enforce_rate_limit`'s `key=` field too.

## [0.1.6] — Login brute-force budgets

Third finding from the v0.1.3 security review. The previous two were
about the rate limiter's plumbing — which address it keys on, what
keying costs. This one is about the login budget itself being spendable
by the wrong person.

### Fixed

- **A successful login cleared the whole address's failed-login budget.**
  Login was limited per address, and `login_rate_limiter.reset(ip)` on
  success wiped that address's counter — including failures recorded
  against completely unrelated accounts. Anyone holding an account of
  their own could therefore spend four guesses on a victim, log in as
  themselves to zero the counter, and repeat indefinitely. The intended
  5/min became roughly the global backstop's 120/min, a ~20x
  amplification, and the reset was reachable by design rather than by
  any trick.

  The budget is now keyed per **(address, username)** — logging in as
  yourself clears only your own pair. The username is case-folded when
  building the key, so capitalisation can't mint fresh budgets: today's
  lookup is case-sensitive, but `=` on text is case-*insensitive* under
  some collations (MySQL's default, Postgres with citext) and
  `DEPLOYMENT.md` already points at Postgres. The two parts are joined
  with NUL, because login takes the username straight off an OAuth2 form
  with no validation and an ordinary separator would let one pair's key
  collide with another's.

- **Added: a per-address failed-login budget** (`LOGIN_IP_FAILURE_LIMIT_PER_MINUTE`,
  default 20/min). This is not a separate improvement — it is the other
  half of the fix above, and shipping the re-keying without it would
  have traded one hole for another. Per-pair keying on its own means one
  address gets 5 guesses *per username*, i.e. no total cap at all on
  password spraying (one common password against thousands of accounts),
  with only the 120/min global backstop underneath. The two budgets
  answer different attacks: the pair budget bounds how hard one account
  can be hammered, the address budget bounds how much guessing one
  address can do at all.

  Only failures are charged to it, and it is never reset. That is what
  makes it safe to set well below the global backstop: people logging in
  successfully never touch it, so a shared address — office NAT, mobile
  CGNAT, a household — doesn't accumulate a budget just by being busy.

  Supporting this needed `RateLimiter.is_exhausted()` (test a budget
  without spending from it) and `.record()` (spend without testing),
  plus `enforce_rate_limit(..., record=False)` so the 429 response shape
  still comes from one place.

  Ten tests. The end-to-end replay of the bypass fails against the
  pre-fix code (`assert 401 == 429` — the sixth guess sailed through
  because the attacker's own login had restored the budget). The
  spraying and never-charged-for-success tests cover the new budget; the
  case-folding test is a guard rather than a reproduction, since
  address-only keying passed it vacuously.

## [0.1.5] — Rate limiter memory

Second finding from the v0.1.3 security review, and the other half of the
attack v0.1.4 closed: that one was about *which* address the limiter
keys on, this one about what keying on an address costs.

### Fixed

- **The rate limiter's attempt table only ever grew.** `check()` pruned
  expired timestamps for the key it was asked about, but nothing ever
  removed a key from `_attempts` — so every distinct client address seen
  since process start kept an entry for the life of the process,
  including entries already pruned down to an empty list. Steady traffic
  leaked slowly; a caller rotating addresses grew it deliberately, and
  rotating addresses is cheap from any IPv6 allocation (a single /64
  hands out more addresses than all of IPv4). Nothing in the limiter
  could push back, because each request arrived under a *new* key and so
  never met a budget.

  `check()` now sweeps the table at most once per window, dropping keys
  whose attempts have all aged out. Memory is therefore bounded by the
  distinct keys seen **within one window** instead of by every key seen
  ever.

  The sweep collects only spent keys, and that restraint is the design,
  not an implementation detail: a key survives unless every one of its
  attempts has expired, so re-checking a swept key computes exactly what
  it would have computed from the expired timestamps left in place. The
  sweep changes memory, never a limiting decision — in particular it can
  never hand a throttled caller a fresh budget. That rules out the
  obvious alternative, an LRU/size cap: capping evicts *live* entries
  under pressure, which is precisely the state an attacker generating
  keys is in, so they could push their own throttled entry out and start
  over. Collecting only expired entries has no such failure mode.

  Honest about the remaining bound: it's a function of traffic, not a
  constant. A burst from many addresses inside one window is still held
  until that window turns over. Making it constant, and shared across
  instances, is the same Redis-backed answer already noted for the
  limiter's multi-instance gap.

  Ten tests, five of which fail against the pre-fix code (the leak
  itself, plus the end-to-end shrink). The other five are guards on the
  safety properties rather than reproductions — they pass either way
  today, and exist so that a future "let's just cap the table" change
  fails loudly.

## [0.1.4] — Client address resolution behind proxies

First finding from a fresh adversarial read of the codebase at v0.1.3.

### Fixed

- **Every per-IP rate limit could be bypassed with a forged header.**
  The image ran uvicorn with `--forwarded-allow-ips "*"`, on the
  reasoning that Railway/Render/Fly always have their proxy in front so
  trusting it is safe. The flag doesn't mean that. With `"*"`, uvicorn
  rewrites `request.client` from the **leftmost** `X-Forwarded-For`
  entry — the end of the chain furthest from the proxy, written by
  whoever sent the request. Since `client_ip()` keys on
  `request.client.host`, a different random address per request bought a
  fresh budget on *every* limiter in the app: login's 5/min brute-force
  protection, register, password reset, `/translate`, and the app-wide
  backstop. It also meant the `ip=` field in every security log line was
  attacker-authored, and — because `RateLimiter` never evicts keys — that
  a single caller could grow the limiter's dict without bound.

  The header is now read by the app itself (`client_ip()` in
  `app/services/rate_limiter.py`) and counted from the **right**: each
  proxy appends the address of its own immediate peer, so with
  `TRUSTED_PROXY_HOPS` proxies in front, the real client is that many
  entries from the end and everything to the left is ignored. Entries
  must parse as IP addresses — an unparseable one, or a chain shorter
  than the configured hop count, falls back to the socket peer, which
  over-limits rather than under-limits. Parsed addresses are also
  normalized, so respelling an IPv6 address doesn't buy a second budget.

  `TRUSTED_PROXY_HOPS` defaults to **0** (no proxy — correct for local
  dev and `docker compose`, where the browser reaches the backend
  directly). Deployments behind one proxy set 1; `DEPLOYMENT.md` explains
  how to count, which direction is safe to get wrong, and how to verify
  both failure modes after deploying — the old guide asserted the
  Dockerfile "handles this", which was exactly the misreading that caused
  the bug. The uvicorn flags are gone from the image; nothing else needed
  them, since this app reads `request.url.path` only and builds no
  absolute URLs.

  Test coverage, and its honest limit: the resolution logic is pinned
  directly (which entry becomes the key, ports stripped, IPv6 normalized,
  fallbacks), plus end-to-end checks that an unconfigured deployment
  ignores the header on the login and `/translate` limiters. Those
  end-to-end tests can't reproduce the *original* bypass, because
  uvicorn's `ProxyHeadersMiddleware` is installed by the server rather
  than by `app.main:app`, so `TestClient` never runs it — they would have
  passed before the fix too. The flag is therefore guarded where it
  actually lives: a deployment-contract test that fails if any
  `--forwarded-allow-ips` returns to the Dockerfile's `CMD`, and another
  that fails if `DEPLOYMENT.md` stops documenting the setting.

## [0.1.3] — PWA support & content expansion

Two roadmap items, and a quiet full circle: the Turkish course written
this version is the first real content to exercise the İ/I case-folding
bug fixed back in the v0.0.7 review — and it now has tests proving a
learner with caps lock on gets scored correctly.

### Added

- **PWA support** (`vite-plugin-pwa`): web app manifest, generated icon
  set (192/512 plus a dedicated **maskable** 512 with a 20% safe zone —
  Android crops icons to its own shape and would otherwise clip the
  glyph), Apple touch icon, favicon, and a Workbox service worker
  precaching the app shell. Three deliberate choices:
  `registerType: "prompt"` rather than autoUpdate, because silently
  swapping the app mid-quiz would lose unsubmitted answers, so the
  person decides when to reload (`UpdatePrompt` component, ARIA-live,
  positioned opposite the toast corner so the two never collide);
  **API responses are not cached** — history, streaks, and quiz sessions
  are per-user and time-sensitive, and a stale-served session would break
  the v0.0.9 served-set grading contract, while the Redis layer already
  caches the one thing worth caching server-side where invalidation is
  manageable; and service workers stay **off in dev**, because a stale SW
  is a genuinely confusing debugging experience.
- **Content as data, not code** (`backend/content/*.json` +
  `app/services/content_import.py` + `scripts/import_content.py`):
  continuing the v0.0.9 move away from a hardcoded catalogue, real
  content now ships as validated JSON packs importable into any database
  without a code change or deploy. `seed_data` is left exactly as it was
  — it's the minimal demo/test fixture that 148 tests depend on.
  Validation runs before any write, so a malformed pack fails loudly and
  atomically: unknown question types, multiple-choice answers missing
  from their own options, and `sentence_order` words that can't
  reconstruct the expected sentence are all caught at load time rather
  than in front of a learner. Imports are idempotent by
  (language, title), so re-running after a deploy is a no-op.
- **Two content packs**, roughly tripling the catalogue: *Turkish for
  Beginners* (A1, 3 lessons — greetings, numbers, food; 15 vocabulary
  items, 13 questions across all four question types) and *Spanish: Out
  in the World* (A2, 2 lessons — restaurant and travel; 10 items, 8
  questions). Both carry real grammar and cultural notes (agglutination,
  vowel harmony, 'hoşça kal' vs 'güle güle', `quisiera` as the polite
  workhorse).
- 9 new tests (157 total, 93% coverage): pack validation, full
  content-tree import, idempotency, public-API serving, and a
  parametrized end-to-end check that `mısır`, `MISIR`, `Mısır`, and a
  padded variant are all accepted while `misir` is correctly rejected —
  verified to be a *meaningful* test (plain `.lower()` folds `MISIR` to
  `misir` and would fail it).

### Fixed — E2E suite (first verified green run)

The webServer fix landed and the E2E test finally *ran* in CI — and
promptly failed on three real defects in the spec itself. All three were
found by running the suite locally against a Chromium already cached on
disk, which is the first time this suite has been executed rather than
merely authored.

- **The login step raced the page navigation.** The spec clicked "Log
  in" and immediately called `page.goto("/")`, tearing down the page
  context while the login request was still in flight: the server logged
  a successful login while the client never persisted the tokens, so
  every later step ran anonymously and the "Saved to your translation
  history" notice never appeared (it is driven by auth *state*, not just
  a stored token). The spec now waits for the visible "Log out" control
  before continuing — and again after the deliberate reload, which
  doubles as proof that the session survives one.
- **Two strict-mode violations from substring matching.** `getByText("100%")`
  matched both the score and the freshly-awarded badge's description
  ("Scored 100% on a quiz."), and on the history page `getByText("hello
  world")` matched both the source text and the translation containing
  it. Both are now `{ exact: true }` — and since a perfect run really
  should award the badge, that assertion was added rather than dodged.
- **`E2E_CHROMIUM_PATH`** escape hatch in `playwright.config.ts`: point
  the suite at an existing browser where `npx playwright install` is
  blocked by network policy. Unset in CI, which keeps using the version
  Playwright manages.

Verified: three consecutive local runs pass (~5s each), unit tests and
the production build stay green.

### Fixed — CI pipeline

Both frontend CI jobs had been red since v0.1.2 introduced them. Neither
failure was in application code; both were in the test *plumbing*, and
one of them had been invisible locally for a bad reason.

- **Vitest was collecting the Playwright spec.** Vitest's default include
  glob is repo-wide, so `e2e/learner-journey.spec.ts` matched, and
  Playwright's `test()` threw "did not expect test() to be called here" —
  failing the run even though all 16 unit tests passed. Fixed by scoping
  `include` to `src/`; the two suites are different runners with
  different globals. *Why it wasn't caught:* the local verification runs
  piped vitest through `grep "Tests " | tail -1`, which printed
  `Tests 16 passed` and swallowed the `Test Files 1 failed` line directly
  above it — a filter that hid exactly the line that mattered, across
  three versions.
- **Playwright's webServer timed out in CI.** Both servers now bind
  explicitly to `127.0.0.1` instead of relying on the default
  `localhost`. On a host with IPv6 — every GitHub runner, but not the
  dev sandbox this was verified in, which has none — `localhost` can
  resolve to `::1` first, leaving the server on `[::1]:5173` while
  Playwright polls `http://127.0.0.1:5173` until the timeout expires.
  Timeouts also raised to 120s (a cold runner pays for Alembic
  migrations and Vite's dependency pre-bundling), and `stdout`/`stderr`
  are now piped. That last part matters for diagnosis: Playwright's
  `stdout` default is `ignore` while uvicorn logs to stderr, so the
  original job log showed backend startup and *nothing at all* from
  Vite — which looked like evidence Vite never started, when it was
  simply muted. The next run will show either its banner or its error.

Honest status: the Vitest fix is verified locally (exit 0, 16 tests, e2e
no longer collected) and the Playwright config is verified to still bring
both servers up. The IPv6 diagnosis cannot be reproduced in an
environment without IPv6, so it remains the leading hypothesis rather
than a proven root cause — the piped output exists so the next CI run
settles it either way.

### Fixed — post-release scan

A full re-read of the codebase at v0.1.3, focused on the seams where the
last three versions meet. Everything below was reproduced before being
fixed, and each now has a regression test:

- **CORS rejected the origin the E2E suite actually browses from.** To a
  browser, `http://localhost:5173` and `http://127.0.0.1:5173` are
  different origins. v0.1.0 locked the allowlist to the former;
  v0.1.2's Playwright config browses the latter — so every API call in
  the E2E journey would have been blocked (verified: no
  `access-control-allow-origin` header, and preflight with an
  `Authorization` header answered **400**). The suite could not have
  passed in CI. Fixed with a proper allowlist:
  `CORS_ALLOWED_ORIGINS` (comma-separated) wins outright in
  deployments, while the development default covers the configured
  frontend plus both spellings of the Vite dev server.
- **The Docker image didn't ship the content packs.** v0.1.3 added
  `backend/content/` and told operators, in `DEPLOYMENT.md`, to run
  `scripts/import_content.py` inside the container — but the Dockerfile
  (written in v0.1.0) never copied the directory. Worse than a plain
  failure: `available_packs()` on a missing directory returns empty, so
  the script **exited 0 having imported nothing**, and the deploy log
  read as success. Fixed both halves: the image copies `content/`, and
  the script now fails loudly when it finds no packs. A test asserts the
  Dockerfile still carries the COPY.
- **Cached translations would survive the switch to the real model.**
  The cache key was `(source, target, sha256(text))` with no notion of
  *which service produced the entry*, so every phrase translated by the
  mock would keep being served as a genuine translation for the full
  7-day TTL after NLLB is switched on — precisely the transition the
  cache exists for. Keys now carry a backend id and a version
  (`TRANSLATION_CACHE_VERSION` as a manual invalidation knob).
- **Browsing lessons minted throwaway quiz sessions.** The lesson page
  probed "does this lesson have a quiz?" with an *authenticated* call,
  and authenticated quiz fetches record a `QuizSession` by design —
  measured: 10 page views produced 10 sessions with zero quizzes taken.
  Noted as harmless in v0.0.9 when there was one lesson; with the v0.1.3
  content packs it became unbounded write traffic from pure reading. The
  probe is now anonymous (existence doesn't depend on who's asking) and
  creates no state.
- **nginx hardening for the PWA**: an explicit `application/manifest+json`
  MIME type (a manifest served as `application/octet-stream` is ignored
  by browsers, silently costing installability), plus `no-cache` on
  `index.html` and `sw.js` — a cached shell pins users to a stale asset
  manifest and a cached service worker means the update prompt never
  appears no matter how often the app is redeployed.
- 11 new tests (168 total).

### Changed

- Version bumped to 0.1.3.

## [0.1.2] — Test depth: frontend units, E2E, load

The version where "tested" stops meaning "the backend is tested". Every
layer now has its own suite, its own question, and — for the load layer —
actual measured numbers. `TESTING.md` is the map (and closes the test-plan
item on the graduation-deliverables list).

### Added

- **Frontend unit tests** (Vitest + React Testing Library, 16 tests):
  first frontend tests in the project's history. Priority went to the
  highest-risk client logic — `api/client`'s token refresh, including a
  concurrency proof that N simultaneous 401s share exactly **one**
  refresh call (single-use refresh tokens mean two racing rotations
  would trip the backend's reuse detection and kill the session); toast
  lifecycle and ARIA escalation; the persist-only-on-explicit-toggle
  theme rule; the blocked-clipboard failure path; sentence building with
  duplicate words. `vitest.config.ts` is separate from the build config
  on purpose. One lesson encoded in a comment: plain `fireEvent` beats
  `userEvent` where fake timers are in play — userEvent's internal
  delays deadlock against a faked clock.
- **Playwright E2E** (`frontend/e2e/`): boots the real backend (fresh
  throwaway SQLite, seeded) and the Vite dev server, then drives
  Chromium through the whole learner journey — login, live translation,
  the session-graded quiz answered to 100%, history, dark-mode toggle.
  Selectors ride the v0.1.1 accessibility work (labels, roles, fieldset
  legends). The test user registers via API by design. **Environment
  honesty:** the browser download is blocked in the local sandbox
  (verified, not assumed), so the suite is authored here and *executed
  in CI* — a new `e2e` job installs Chromium and uploads traces on
  failure.
- **Locust load testing** (`backend/loadtest/`) plus the knob that makes
  it honest: rate-limit budgets moved to settings
  (`API_RATE_LIMIT_PER_MINUTE`, `TRANSLATE_RATE_LIMIT_PER_MINUTE`,
  defaults unchanged) because single-IP load generation and per-IP
  limiting are fundamentally at odds. Both modes were actually run:
  defaults → 227 requests, 152 × 429 after the first 76 served
  (`/translate`'s budget first, then the global backstop; rejections
  cost 1–5 ms) — the limiter verified under pressure; raised budgets →
  349 requests, 0 failures, p50 16 ms / p95 93 ms at ~11.6 req/s
  (mock service + SQLite baseline). All simulated users share one
  pre-created account so the auth limiters don't eat the run.
- **`TESTING.md`**: the four-layer strategy, how to run each, the real
  numbers, and the gaps kept honest (register-form E2E, no axe/visual
  automation, Postgres untested).
- CI: `frontend-build` now runs the unit suite before the build; new
  `e2e` job.

### Changed

- Version bumped to 0.1.2.

## [0.1.1] — UX round: dark mode, toasts, clipboard, accessibility audit

Pure frontend version. The headline is less "dark mode exists" and more
what the accessibility audit dug up — including the fact that the *light*
theme had been shipping WCAG failures since v0.0.2.

### Added

- **Dark mode**, defined entirely at the token layer: every component
  already styled itself through `tokens.css` custom properties, so the
  theme is one `[data-theme="dark"]` block — pages don't know it exists.
  An inline script in `index.html` resolves the theme *before first
  paint* (stored choice, else system preference; no white flash),
  `color-scheme: dark` flips native controls, and the NavBar toggle
  persists **only on explicit use** — someone who never touches the
  switch keeps following their system preference instead of being locked
  to a snapshot of it. One deliberate exception: the achievement chip is
  pinned to its brand colors (navy + gold) in both themes, because
  letting its tokens invert would have sunk the gold title to a measured
  1.6:1.
- **General toast system** (`ToastContext`, `useToast`): fixed-viewport,
  auto-dismissing (success 4s, errors 7s — people need time to read what
  went wrong), dismissible, announced via `aria-live` with `role="alert"`
  escalation for errors. Coexists with `AchievementToast` on purpose:
  that one is an inline, in-page celebration; this is the app-wide
  transient channel. Wired to real events — copy actions, "Daily goal
  updated", "Signed out" — not just built and left on a shelf.
- **Copy to clipboard** (`CopyButton`): on the translation output and on
  every history row; failure (blocked clipboard) reports via an error
  toast instead of silently doing nothing.

### Accessibility audit — the ledger

Found and fixed:

- `<html lang="tr">` on an entirely English UI — screen readers were
  being told to pronounce everything with Turkish rules. Now `en`.
- The translate textarea and the daily-goal input had no accessible
  name (placeholder-only). Labeled.
- No `<main>` landmark and no skip link; keyboard users had to tab
  through the nav on every page. Both added.
- The translation output — the entire point of the page — was never
  announced to screen readers. Now `role="status"` + `aria-live="polite"`
  + `aria-busy` while in flight.
- Two files carried hardcoded `#fff` (dark-mode landmines); tokenized to
  `--paper-0`, which also *improves* contrast on filled states in dark.
- Brand amber as text failed AA everywhere it appeared (~2.6:1 on
  white). New `--accent-text` token (`#87621f` light / `#e8c07a` dark),
  swapped in at every amber-text site.
- **The shipped light palette itself failed AA in five measured pairs**:
  `error-500`-on-`error-100` 3.66, `success-500`-on-`success-100` 2.99,
  light-text-on-filled error 4.09 and success 3.17, and the accent badge
  4.43. Fixed by solver-computed darkening (`--error-500` → `#bc3c3c`,
  `--success-500` → `#247b4d`) satisfying both text-on-tint and
  filled-state constraints at once; all 30 audited pairs now pass in
  both themes, with the rationale committed as comments in `tokens.css`.

Verified already correct (worth recording): quiz radio groups use
`fieldset`/`legend`; `LoadingState`/`ErrorState` carry
`role="status"`/`role="alert"`; mic/speaker buttons have proper
`aria-label` + `aria-pressed`; `:focus-visible` and a global
`prefers-reduced-motion` rule were in place since v0.0.2.

Deferred, on the record: per-page `document.title`; a real
browser/axe/screen-reader pass (queued with Playwright in v0.1.2); the
`theme-color` meta follows the system, not the manual toggle.

### Honest limits

- Verified by strict TypeScript build and static WCAG contrast
  computation — no browser in this environment, so no rendered-pixel or
  assistive-tech verification yet.

### Changed

- Version bumped to 0.1.1.

## [0.1.0] — Docker, Redis cache & first deploy

The minor-version bump is earned: this is the release where the system
becomes a deployable product instead of a two-terminal dev setup, and
where the last "before production" item from the security audit gets
closed in the version it was always scheduled for.

### Added

- **Docker + docker-compose, one command** (`docker compose up --build`):
  backend image (python-slim, non-root user, `HEALTHCHECK` against the
  rate-limit-exempt `/health`, startup migrations already handled by
  `init_db`), frontend image (two-stage: Node build → nginx with SPA
  fallback and immutable-asset caching), Redis, and a named volume so
  SQLite survives container replacement. Uvicorn runs with
  `--proxy-headers` so rate limiting and security logs see real client
  IPs behind platform proxies — the deployment concern promised in the
  v0.0.8 `client_ip()` comment, now paid off (with the trust tradeoff
  documented in the Dockerfile).
- **Redis translation cache** (`app/services/translation_cache.py`):
  read-through cache keyed on `(source, target, sha256(text))`. Two
  load-bearing rules: disabled unless `REDIS_URL` is set (dev/tests need
  no Redis), and a cache failure can only ever mean a cache *miss* —
  short timeouts, broad catches, translations never break because Redis
  did. Only the model output is cached; history, achievements, and idiom
  warnings run on every request, and there's a test proving a cache hit
  still records history. Ceremonial with the mock service; the whole
  point once real NLLB inference is on.
- **CORS locked down**: `allow_origins` is now the configured
  `FRONTEND_BASE_URL` instead of `"*"` — closing the one
  must-fix-before-production finding from the v0.0.7 OWASP audit
  (SECURITY.md A05 updated).
- **`DEPLOYMENT.md`**: Railway/Render/Fly for the backend (env-var table,
  SQLite-volume vs Postgres tradeoff, SMTP), Vercel/Netlify for the
  frontend (`vercel.json` SPA rewrite, build-time `VITE_API_URL`),
  secrets-management rules, and a post-deploy checklist — which also
  closes the "prod env/secret management guide" roadmap item.
- 7 new tests (148 total, 93% coverage): cache unit behaviour (disabled,
  roundtrip, per-language keys, corrupted entries, outage degradation)
  and the endpoint contract (hit skips the model, never the history).

### Honest limits

- No Docker daemon in this environment: images and compose were
  validated by inspection and YAML parsing, not by an actual
  `docker compose up`. First local run may surface small friction.
- The Postgres path is documented and dependency-commented
  (`psycopg2-binary`) but untested — the migration chain is CI-verified
  on SQLite only.

### Changed

- Version bumped to 0.1.0; README rewritten around a compact
  version-history table (the per-version detail stays here).

## [0.0.9] — Alembic migrations, quiz sessions & admin API

The schema-discipline version. create_all served through v0.0.8, but it
can only add missing tables — it cannot express "add a column", and this
version needed exactly that twice. So migrations arrived first, and the
two features that required schema changes rode in on them.

### Added

- **Alembic migrations** (`backend/alembic/`): two revisions — `0001`
  captures the full pre-0.0.9 schema, `0002` adds `quizsession` and
  `user.is_admin`. Startup (`init_db`) now runs `upgrade head`
  programmatically instead of `create_all`; the CLI works too
  (`alembic upgrade head` from `backend/`), with the URL resolved from
  app settings in both paths (`alembic.ini` deliberately leaves
  `sqlalchemy.url` empty — an inline value there would silently win).
  Two hard-won footnotes are encoded in the files themselves:
  autogenerate omits `server_default`, so the `is_admin` migration adds
  it by hand (a NOT NULL column can't join a populated table without
  one, verified against a database with existing rows); and
  `render_as_batch=True` is on because SQLite can't ALTER TABLE
  natively. A migration-drift test upgrades a scratch database to head
  and asserts the result matches the SQLModel metadata exactly — a model
  change that forgets its migration now fails the suite instead of the
  deployment. **Existing pre-0.0.9 dev databases**: delete `app.db`, or
  run `alembic stamp 0001` once and upgrade from there.
- **Quiz sessions — the real fix for the scoring exploit** flagged in
  the v0.0.7 review and deliberately deferred until migrations existed.
  Fetching a quiz while logged in now records the exact served question
  set as a `QuizSession`; submissions carry `session_id` and are graded
  against that served set. This *reverses* the documented v0.0.6 choice
  of grading only submitted answers: unanswered served questions count
  as wrong, answers outside the served set are ignored, and submitting
  one cherry-picked answer now scores 20%, not 100% — no more free
  `perfect_quiz` badges. Sessions are reusable on purpose ("Try again"
  is practice, not an exploit) and one rejection message covers
  missing/foreign/mismatched sessions (no session-id probing).
  **Breaking change** to `POST /quizzes/{id}/submit`; frontend updated
  in lockstep.
- **Admin content-management API** (`/admin/*`, 15 endpoints): full CRUD
  for courses, lessons, vocabulary, quizzes, and questions — the
  catalogue is no longer hardcoded seed data. Authorization is a plain
  `is_admin` flag with no API path to it (promotion only via
  `scripts/make_admin.py`, sidestepping the who-admins-the-first-admin
  bootstrap problem; `UserCreate` has no such field, so no mass
  assignment). Deletes cascade explicitly and destructively — course →
  lessons → vocabulary (including learners' spaced-repetition progress)
  → quizzes → questions/attempts/sessions — a documented product
  decision, with soft-delete noted as the roadmap answer if learner
  data must survive content edits. One quiz per lesson is enforced (the
  public lesson→quiz lookup would otherwise be ambiguous).
- 15 new tests (141 total, coverage 93%): migration drift, session
  creation/authorization/reuse, the closed exploit, admin authz +
  mass-assignment guard, the full content pipeline, and cascades.

### Security — post-release dependency response

The security-scan workflow did its job: it failed on real findings, four
pushes in a row, until they were dealt with. Both were resolved by
removing the vulnerable code from the tree rather than allowlisting it:

- `python-jose` -> `PyJWT` (2.13.0): pip-audit flagged the transitive
  `ecdsa` package (PYSEC-2026-1325) with *no fix version upstream*. The
  v0.0.7 audit had already verified this app's HS256-only signing never
  touches ECDSA code -- which is exactly what made a drop-in migration
  safe. Four changed lines in `app/security.py`, one dependency line,
  and the flagged package is simply gone (along with a sparsely
  maintained JWT library).
- Vite 5 -> 8 (+ @vitejs/plugin-react 4 -> 6): resolves the `esbuild`
  dev-server advisory that had been consciously deferred as
  breaking-upgrade-only; `npm audit` now reports zero vulnerabilities
  and the production build still passes (faster, too: ~0.7s vs ~2.3s).
- Workflow runtimes: action majors bumped (checkout v5, setup-python v6,
  setup-node v5) and CI Node 20 -> 22, addressing the Node 20 runner
  deprecation warnings and Vite 8's engine floor in one move.
- `SECURITY.md` and `frontend/README.md` updated so the accepted-risk
  notes tell the full story: assessed first, eliminated after.

### Changed

- Version bumped to 0.0.9 (backend config + frontend package).

## [0.0.8] — Test infrastructure & backend polish

The "cheapest insurance first" version: before any more features land,
every push now has to survive the full test suite and a frontend
type-check, and the API gets the two small pieces of production hygiene
flagged during planning — rate limiting beyond the auth endpoints, and
pagination on the lists that grow.

### Added

- **CI workflow** (`.github/workflows/ci.yml`): two jobs on every push
  and pull request — backend `pytest` with coverage (pytest-cov,
  `--cov-fail-under=88`; currently at 94%) and frontend `tsc -b && vite
  build`. The security-scan workflow keeps its own schedule; this one is
  the regression net that protects every version after it.
- **App-wide rate limiting**: a per-IP backstop across the whole API
  (120 req/min via `GeneralRateLimitMiddleware`; `/health` exempt because
  deployment platforms poll it and a health check that can 429 reads as
  an outage) plus a tighter 30/min budget on `/translate` — the endpoint
  that will eventually run real model inference, and therefore the most
  expensive thing an abuser can call. Enforcement (429 + `Retry-After`,
  which all rate-limited responses now carry, auth included) moved out of
  the auth router into `app/services/rate_limiter.py` so any router can
  rate-limit an endpoint in one line.
- **Pagination** on `/courses` and `/translate/history` via a shared
  `Page[T]` envelope (`items`, `total`, `limit`, `offset`; limit 1–100,
  default 20, newest-first for history). **Breaking change** for both
  endpoints: responses are now envelopes, not bare arrays. Frontend
  updated in the same version — history gets a "Load more" control with a
  "showing X of Y" count, courses request one generous page.
- 8 new tests (126 total): envelope shape, limit/offset slicing,
  parameter validation, history ordering, translate + backstop limiters,
  `/health` exemption, `Retry-After` presence.

### Changed

- Version bumped to 0.0.8 (backend config + frontend package).

## [0.0.7] — Security

Completes the "Güvenlik" topic. Six items:

- **Refresh tokens + revocation**: JWT access tokens shortened from 24h to
  30 minutes; sessions now stay alive via a separate, server-side-revocable
  refresh token (new `RefreshToken` table, hash stored not plaintext).
  `POST /auth/refresh` rotates the token on every use; presenting an
  already-rotated (revoked) token — the signature of a replayed/stolen
  token — now revokes *every* active session for that user as a
  precaution. `POST /auth/logout` and `/auth/logout-all` added. Frontend's
  API client now refreshes and retries automatically on a 401, with
  concurrent requests sharing one in-flight refresh call instead of racing
  each other.
- **Rate limiting**: hand-rolled in-memory sliding-window limiter
  (`app/services/rate_limiter.py`) on `/auth/login` (5/min), `/auth/register`
  (5/min), and `/auth/request-password-reset` (3/5min). Documented
  limitation: in-process memory, so it doesn't share state across multiple
  worker instances — fine for this single-process deployment, would need
  Redis for a horizontally-scaled one.
- **Email verification + password reset**: new `EmailService` abstraction
  (mock in this sandbox — no SMTP credentials or network access to a mail
  provider here; a real `SMTPEmailService` is written but unexercised).
  `User.is_verified`, single-use hashed tokens (`AuthToken` table) for both
  flows. Password reset deliberately returns the same generic response
  whether or not the email is registered, to avoid account enumeration —
  and revokes all existing sessions on completion. New frontend pages:
  `/forgot-password`, `/reset-password`, `/verify-email`.
- **Security headers**: `SecurityHeadersMiddleware` adds CSP,
  X-Frame-Options, X-Content-Type-Options, Referrer-Policy,
  Permissions-Policy, and HSTS to every response.
- **CI dependency scanning**: `.github/workflows/security-scan.yml` runs
  `pip-audit` and `npm audit` on every push/PR and weekly on a schedule.
- **OWASP Top 10 audit** (`SECURITY.md`): a real review of this specific
  codebase against all 10 categories, not a generic checklist. Real
  findings: CORS wildcard (dev-only, must be restricted before production),
  a weak default `SECRET_KEY` (now warned about at startup), a
  registration-enumeration trade-off, and a transitive `ecdsa` CVE that I
  verified — empirically, by checking which modules actually get imported
  at runtime — is not reachable through this app's HS256-only JWT usage.
- Also added: structured security event logging
  (`app/services/security_logging.py`) for login attempts, rate-limit
  hits, token reuse detection, and the auth flows above.
- Caught and fixed two real bugs while building this: (1) the same
  `is None` vs `.is_(None)` SQLAlchemy mistake as v0.0.6's stats bug,
  repeated in the new refresh-token code, and (2) SQLite round-trips
  datetime columns as naive even though every write path stores UTC-aware
  ones, which raised `TypeError` comparing token expiry against "now"
  until a small `_as_aware_utc()` helper normalized it.
- 21 new tests (106 total).

### Fixed — post-review bug-fix pass

A full read-through of the codebase after the security work, hunting for
bugs rather than adding features. Findings, worst first:

- **Expired sessions silently downgraded to anonymous**:
  `get_current_user_optional` swallowed *invalid* tokens and returned
  None, the same as no token at all. Consequence: ~30 minutes after
  login (access-token expiry), `/translate` kept returning 200 — but as
  an anonymous request, so nothing was saved to history (while the UI
  kept saying "Saved to your translation history") and adaptive quiz
  difficulty switched off. The frontend's refresh-and-retry only reacts
  to a 401, which this path never produced. Now: no token → anonymous;
  a token that is present but invalid → 401, which correctly triggers
  the refresh flow.
- **Adaptive difficulty was never active in the UI**: the frontend's
  `getQuizByLesson` call didn't send the Authorization header at all, so
  the backend always served the unfiltered anonymous question set.
  One-line fix (`auth: true`), found by reading, confirmed by the code
  path.
- **Turkish İ/I case folding**: `"BAŞINI YEDİ"` produced no idiom
  warning because Unicode default lowercasing maps I→i (not ı) and
  İ→i+combining-dot. New `app/services/text_normalization.py` applies
  Turkish-specific capital mappings before `casefold()`, used by both
  idiom matching and quiz answer comparison (which resolves the quiz's
  language via its course). Bonus from switching lower()→casefold():
  German ß/SS now compare equal.
- **Email verification page showed failure after success**: React 18
  StrictMode runs effects twice in development; the second POST hit the
  (by-design single-use) token, got a 400, and overwrote the first
  call's success state. Guarded with a ref.
- **Network blips logged people out**: AuthContext cleared tokens on
  *any* `/auth/me` failure at mount, including the backend simply being
  down. Now only a real 401/403 clears the session.
- **Stale `vite.config.js` shadowed `vite.config.ts`**: `tsc -b` was
  emitting `vite.config.js`/`.d.ts` into the project root (gitignored,
  but present on disk — and Vite loads `.js` before `.ts`, so edits to
  the real config would silently do nothing). Emission redirected via
  `emitDeclarationOnly` + an `outDir` inside `node_modules/`.
- Smaller: registration race on the unique username/email constraint now
  returns the same 400 as the fast path instead of a 500; a signed token
  with a malformed `sub` claim is a clean 401 instead of a ValueError
  500; `microphone=()` removed from the Permissions-Policy header (the
  app's own speech features need the mic if the SPA is ever served from
  the API's origin); the daily-goal editor validates its 1–200 bounds
  and reports save failures instead of failing silently.
- Known design weakness, documented but deliberately *not* changed here:
  quiz scoring grades only the submitted answers (a tested, documented
  choice made for adaptive-subset consistency), which allows submitting
  a single known answer for a 100% score and the `perfect_quiz` badge.
  The proper fix is a server-side record of which questions were served
  per attempt — a schema change that belongs with the planned Alembic
  migration work, not a silent contract change in a bug-fix pass.
- 12 new regression tests (118 total).

## [0.0.6] — Language learning / pedagogy

Completes the "Dil öğrenme / pedagoji" topic. One item was already covered
and needed no new work — flagging that explicitly rather than padding out
a redundant feature:

- **Flashcard mode**: already delivered in v0.0.4 as the `/review`
  spaced-repetition flow (see word → reveal → rate). No changes needed.

Everything else:

- **New quiz question types**: `fill_blank`, `listening` (reuses the
  text-to-speech hook built in v0.0.4), and `sentence_order`
  (click-to-build-order UI, new `SentenceOrderInput` component).
  `matching` was considered and deliberately deferred — representing
  match-pairs cleanly wants its own table rather than being squeezed into
  the existing flat question schema, and hacking it in wasn't worth the
  fragility.
  - Scoring for `fill_blank` and `sentence_order` needed zero new backend
    logic: both just compare strings, exactly like the existing
    multiple-choice check.
  - Caught and fixed a real design bug while building this: quiz scoring
    used to grade against *every* question in the quiz, which would have
    unfairly penalized adaptive selection (below) showing only a subset.
    Now grades only what was actually submitted.
- **Adaptive quiz difficulty**: `difficulty` (1-3) added to
  `QuizQuestion`. Question selection now factors in the learner's recent
  average score — comfortably-scoring learners see harder questions,
  struggling learners see easier ones, with a floor that never returns an
  empty quiz. Deliberately simple and explainable (fixed score
  thresholds), not a trained model. Seed data expanded from 1 question to
  5 across 3 difficulty levels so this is actually demonstrable.
- **Achievement badges**: 8-badge catalogue (first translation, 10/100
  translations, first quiz, perfect quiz, 5 words started, 3-day/7-day
  streak) in `app/services/achievements.py`. Checked after translate,
  quiz-submit, and review-submit; newly-earned badges come back in those
  same responses and show up as a toast in the UI.
- **Daily goal**: `daily_review_goal` on `User` (default 10), editable via
  `PATCH /auth/me/goal`, shown as a progress bar against today's review
  count on `/progress`.
- **Lesson content enrichment**: `grammar_note` and `cultural_note` added
  to `Lesson`, populated for the seeded Greetings lesson, shown on the
  lesson page.
- Refactored streak computation out of `app/routers/stats.py` into
  `app/services/streaks.py` — it's now used from two places
  (stats display, streak-badge checking), so importing a "private"
  function across routers stopped being reasonable.
- 18 new tests (85 total).

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
