# Security Review — OWASP Top 10 (2021)

**Scope:** Lingua backend (FastAPI) and frontend (React/TypeScript).
Originally written at v0.0.7; a second adversarial pass at v0.1.3
produced the findings fixed across v0.1.4–v0.1.11, and the sections below
have been brought back in line with the code as part of that.
**Method:** manual source review against each OWASP Top 10 2021 category,
plus automated dependency scanning (`pip-audit`, `npm audit`). Every
finding below was checked against the actual code — not inferred from the
framework being "generally fine" — and every fix claimed was verified
with a passing test.

**On that last sentence:** the v0.1.3 pass found two places where this
document had drifted from the code — a claimed bcrypt fix that was never
written (A07) and an assertion that no admin surface existed six versions
after one shipped (A01). Both are recorded in place rather than quietly
corrected, because how a security document goes wrong is itself worth
knowing: not by being careless at the time, but by staying still while
the code moved.

This is not a substitute for a professional external penetration test (no
dynamic/black-box testing, no fuzzing, no infrastructure review), but it
is a genuine review of this specific codebase, not a generic checklist
filled in from memory.

## Summary

| # | Category | Status |
|---|---|---|
| A01 | Broken Access Control | ✅ No issues found — but this section's own text was wrong until v0.1.11, claiming no admin surface existed six versions after one shipped |
| A02 | Cryptographic Failures | ⚠️ 1 medium (weak default secret, startup-warned); bcrypt's silent 72-byte truncation fixed in v0.1.11; transitive-dep finding resolved post-v0.0.9 (PyJWT) |
| A03 | Injection | ✅ No issues found in data access; security-log injection found and fixed in v0.1.7 (see A09) |
| A04 | Insecure Design | ✅ Rate limiting bypassable via `X-Forwarded-For` (v0.1.4) and its attempt table unbounded (v0.1.5), both fixed; 1 non-security design note |
| A05 | Security Misconfiguration | ✅ CORS wildcard resolved in v0.1.0; `/docs` + `/openapi.json` published unconditionally, fixed in v0.1.10 |
| A06 | Vulnerable/Outdated Components | ✅ both findings resolved post-v0.0.9 (PyJWT, Vite 8); CI-monitored going forward |
| A07 | Auth Failures | ✅ Login response times equalised (v0.1.18, they distinguished real accounts 40x over); a successful login cleared the whole address's brute-force budget (v0.1.6) and refresh-token reuse detection fired on ordinary second tabs (v0.1.8), both fixed; email verification decided as informational rather than enforced (v0.1.12); 1 low (registration enumeration) |
| A08 | Software/Data Integrity Failures | ✅ No issues found |
| A09 | Logging/Monitoring Failures | ✅ Structured logging added in v0.0.7; its values were forgeable until escaped in v0.1.7 |
| A10 | Server-Side Request Forgery | ✅ Not applicable to current feature set |

Nothing here is rated Critical. The v0.1.3 pass raised the count of
Medium findings considerably from what this summary used to claim — six
of them, all now fixed (v0.1.4–v0.1.11) and each with tests. The pattern
worth noting is that five of the six were in code written *as* security
controls: the rate limiter, the reuse detector, the audit log. Defensive
code gets audited least, because its presence reads as the answer.

One Medium remains open by design: the default `SECRET_KEY`, which is
fine in development and **must** be changed before any real deployment —
called out below, in `backend/README.md`, and warned about at startup.
`DEPLOYMENT.md` carries the rest of the settings a deployment has to get
right (`TRUSTED_PROXY_HOPS`, `ENABLE_API_DOCS`).

---

## A01: Broken Access Control

**Checked:** every endpoint that returns or modifies user-specific data —
`/translate/history`, `/users/me/stats`, `/users/me/review-queue`,
`/vocabulary/{id}/review`, `/users/me/achievements`,
`/users/me/vocabulary-suggestions`, `/auth/me`, `/auth/me/goal`.

**Finding:** none. Every one of these scopes its query by `current_user.id`
derived from the validated JWT (see `get_current_user` in
`app/routers/auth.py`), never from a client-supplied ID. `/vocabulary/{id}`
takes an ID in the URL, but that ID identifies a shared catalogue word, not
a user's own resource — the resulting progress record is still correctly
tied to `current_user.id`, so there's no path to read or modify another
user's review schedule by changing the URL.

**Corrected in v0.1.11.** This section used to end: *"There is no
admin/role concept in this app yet, so there's no privilege-escalation
surface to review there — noting that as 'not applicable yet' rather than
silently skipping it."* That stopped being true in v0.0.9, which added
the whole `/admin` content-management API. So the most load-bearing
sentence in this document's access-control section said "nothing to
review here" about the one part of the app that most needed reviewing,
for six versions. Reviewed properly now:

**Checked:** every `/admin` operation — 15 of them across 10 paths,
enumerated from the generated OpenAPI schema rather than spot-checked, so
a route added later cannot quietly escape the check
(`test_every_admin_route_is_gated`).

**Finding:** none. Authorization is a single `is_admin` flag, enforced by
a router-level dependency (`require_admin` in `app/routers/admin.py`), so
it applies to every operation under the prefix rather than being
re-remembered per handler. The flag has no path to being set through the
API: `UserCreate` has no such field, so there is no mass-assignment
route, and promotion happens only via `scripts/make_admin.py` against the
database. Tests cover all three properties — unauthenticated (401),
authenticated-but-not-admin (403), and the mass-assignment attempt.

**Design note (not a vulnerability):** admin deletes cascade
destructively, taking learners' spaced-repetition progress on removed
vocabulary with them. That is a deliberate product decision documented in
`app/routers/admin.py`, with soft-delete as the roadmap answer if learner
data ever needs to outlive content removal.

## A02: Cryptographic Failures

**Passwords:** `bcrypt_sha256` via `passlib` — an appropriately slow,
salted hash, with the input SHA-256'd first so nothing is silently
discarded. Plain bcrypt was used until v0.1.11 and truncated at 72 bytes;
see the finding under A07.

**JWTs:** signed with HS256 (HMAC-SHA256), which is appropriate here since
only this one backend ever needs to verify tokens (no third party needs
asymmetric verification).

**Finding (Medium): weak default `SECRET_KEY`.** `app/config.py` ships a
default value (`"change-this-for-development"`). If a deployment forgets
to override it via `.env`, every JWT becomes forgeable by anyone who reads
this public repository. **Mitigated this version:** the app now logs a
security warning at startup if the default is still in use (see
`app/main.py`). **Not fully closed:** the app still *starts* either way.
A stronger future fix would refuse to start at all when
`ENVIRONMENT=production` and the secret is still the default — tracked as
a recommendation, not implemented here, since this app has no
`ENVIRONMENT` flag yet to hang that check on.

**Refresh / verification / reset tokens:** generated with
`secrets.token_urlsafe(32)` (a CSPRNG, 256 bits of entropy) and stored as
SHA-256 hashes, never in plaintext (`app/services/tokens.py`).

**Finding (Low, transitive, verified not exploitable here):** `pip-audit`
flags `ecdsa` (pulled in transitively by `python-jose`) for
PYSEC-2026-1325, a timing side-channel in `ecdsa.SigningKey.sign_digest()`
that the upstream maintainers have declined to fix (side-channel attacks
are out of scope for that project). **Checked whether this app is
actually affected:** this app signs JWTs with HS256 only. I verified
empirically (not just assumed) that encoding a token with `algorithm="HS256"`
never imports the `ecdsa` module at all in this process — the vulnerable
code path is never reached. Accepted as a non-issue *for this specific
usage*; would need re-review if the JWT algorithm ever changed to an
ECDSA-based one (e.g. ES256).

**Update (post-v0.0.9):** resolved for good rather than left as an
accepted risk -- `python-jose` was replaced with `PyJWT`, which removes
the `ecdsa` package from the dependency tree entirely (and swaps a
sparsely maintained JWT library for the actively maintained standard).
The HS256-only analysis above is exactly what made this safe as a
drop-in change.

## A03: Injection

**Checked:** every database access in the codebase (`grep` for raw
`execute(`, f-string SQL, or string-formatted queries — none found).

**Finding:** none in SQL. All queries go through SQLModel/SQLAlchemy's
parameterized query builder (`select(...).where(...)`); there is no raw
SQL string concatenation anywhere in this codebase.

**Finding (Low), fixed in v0.1.17: the Redis cache key was built by
string concatenation from unvalidated input.** SQL was checked here;
the *other* place this codebase composes a string out of user input was
not. `/translate` accepted arbitrary unbounded `source_lang` /
`target_lang` values — the only user-supplied fields in the app with no
constraint on them — and the cache key is
`translation:v{version}:{backend}:{source}:{target}:{digest}`,
colon-joined with no escaping. Two consequences, both verified:
`("a", "b:c")` and `("a:b", "c")` resolve to the same key, and a caller
could mint unlimited distinct keys in the shared cache. A 500-character
"language code" was also stored verbatim in `TranslationHistory`.

Fixed at the edge rather than by escaping the key: the codes are now
validated against the set the translation engine actually supports, so a
code cannot contain the separator in the first place. The same check
stops unrecognised codes reaching the NLLB tokenizer once the real model
is switched on.

## A04: Insecure Design

**Fixed this version:** the two design-level gaps flagged in the original
project plan — no way to revoke a JWT before natural expiry, and no
brute-force protection on auth endpoints — are both addressed (refresh
tokens with rotation + reuse detection; rate limiting on login/register/
password-reset-request).

**Design note (not a security vulnerability):** achievement badges are
awarded purely on action *counts* (e.g. "10 translations") with no check
on content — someone could submit repeated trivial text to farm badges
quickly. No data exposure or privilege gain results; this is a
gamification-integrity concern, not a security one, but a genuine review
should notice the difference between "checklist says no vulnerability
here" and actually thinking about how the system could be gamed.

## A05: Security Misconfiguration

**Finding (Medium-High): CORS is wide open.** `app/main.py` currently sets
`allow_origins=["*"]`. Since this API uses Bearer tokens rather than
cookies, the classic CSRF risk is lower than a cookie-based session would
carry — but a wildcard origin still means any website's JavaScript can
call this API and read the response if it has a valid bearer token (e.g.
obtained via XSS somewhere else, or a user pasting a token somewhere they
shouldn't). This is explicitly commented as development-only in the code,
but calling it out here in writing: **this must be restricted to the
real frontend origin(s) before any production deployment.**

**Update (v0.1.0):** done, in the deployment version where it belonged —
`allow_origins` now reads the single configured `FRONTEND_BASE_URL`
(default: the local Vite dev origin), and `DEPLOYMENT.md` documents
setting it per environment. The wildcard is gone.

**Fixed this version:** `SecurityHeadersMiddleware` now sets
`X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`,
`Referrer-Policy`, `Permissions-Policy`, and `Strict-Transport-Security`
on every response (`app/middleware.py`).

**Checked:** unhandled-exception behavior. FastAPI's default error
handling doesn't leak stack traces to clients for uncaught exceptions as
long as the app isn't started with a debug/reload flag that changes that.
Recommend explicitly confirming this in whatever process manager runs the
app in production (no code change needed here, but worth stating rather
than assuming).

## A06: Vulnerable and Outdated Components

**Fixed this version:** `.github/workflows/security-scan.yml` now runs
`pip-audit` and `npm audit` on every push/PR and weekly on a schedule, so
a newly-disclosed vulnerability shows up as a CI result instead of
depending on someone remembering to check.

**Findings history:** the two findings from the v0.0.7 audit -- the
`ecdsa` transitive dependency (A02) and the `esbuild` dev-server advisory
in the frontend toolchain -- were first assessed and documented as
accepted risks, then eliminated in the post-v0.0.9 dependency response:
`python-jose` was replaced with `PyJWT` (removing `ecdsa` from the
tree), and Vite was upgraded 5 -> 8 (pulling a patched `esbuild`). Both
audits now pass clean; the workflow gate exists to catch the *next*
disclosure.

**The gate caught the next disclosure (v0.1.22).** Worth recording
because it is the case the workflow was built for and the first time it
actually fired: the scan went red on a commit whose dependency tree had
not changed at all — the lockfile diff across the seven preceding
versions is two lines, both the project's own version string. Three
advisories were published against dependencies that were already there.

- **`brace-expansion` DoS (High, `GHSA-mh99-v99m-4gvg`) — fixed.**
  Reached through `vite-plugin-pwa → workbox-build → glob → minimatch`,
  and separately through `…→ ejs → jake → filelist → minimatch`. npm's
  own remedy was to *downgrade* `vite-plugin-pwa` to 1.2.0, a breaking
  change, because 1.3.0 is the latest release and still carries the
  vulnerable tree. Resolved instead with an `overrides` entry pinning
  `brace-expansion` to the patched 5.0.8 across the tree, which keeps the
  plugin current. Verified rather than assumed: the PWA build still
  generates its service worker with the same 15 precache entries, and all
  80 frontend tests pass.

  Reachability, stated plainly: this is build-time tooling. The patterns
  fed to it come from our own Vite config, not from a request, so it was
  never exposed to an attacker against the deployed app. It was fixed
  because the fix was clean and the policy says High fails the build —
  not because the app was at risk.

- **Two React Router advisories (Moderate) — assessed, deferred.**
  `GHSA-wrjc-x8rr-h8h6` (open redirect via a backslash in `<Link>` /
  `useNavigate`) and `GHSA-337j-9hxr-rhxg` (constructor injection in
  `deserializeErrors()` during SSR hydration). The advisory range covers
  every 6.x release, so the fix is a 7.x major upgrade.

  Neither is reachable here, checked against the code rather than
  assumed. Every `navigate()` call in the app passes the literal `"/"`,
  the only `<Navigate>` targets `"/login"`, and every `<Link>` target is
  either a literal path or an id interpolated *after* a literal prefix
  (`` `/lessons/${lessonId}` ``) — a `useParams` value is
  attacker-influenced, but it lands mid-path, and the open-redirect
  pattern needs the target to *begin* with the backslashes to be read as
  protocol-relative. The second advisory needs SSR hydration; this is a
  Vite SPA on `BrowserRouter` with no `hydrateRoot`, `StaticRouter` or
  `renderToString` anywhere in the tree.

  Deferred rather than rushed: a major router upgrade is real migration
  work, and doing it under time pressure for two advisories that cannot
  fire here is how a routing regression gets shipped. Tracked as work,
  not as an accepted permanent risk — and the `--audit-level=high` gate
  means these stay visible in every scan without blocking pushes.

## A07: Identification and Authentication Failures

**Fixed this version:** rate limiting on `/auth/login` (5/min),
`/auth/register` (5/min), and `/auth/request-password-reset` (3/5min);
refresh token rotation with reuse detection (a replayed, already-rotated
refresh token now revokes every session for that user, not just itself);
short-lived (30 min) access tokens instead of the previous 24-hour ones.

**Checked:** password minimum length (8 characters, enforced both ends);
login's error message is appropriately generic ("Incorrect username or
password", doesn't reveal which was wrong) — and, since v0.1.18, so is
its response *time* (see the finding below).

**Finding (Medium), fixed in v0.1.11: bcrypt silently truncated
passwords at 72 bytes — and this document previously claimed otherwise.**
The text here used to read "the bcrypt 72-byte input handling (already
fixed earlier in this project — see `CHANGELOG.md` v0.0.1)". No such fix
existed: `app/security.py` did a plain
`CryptContext(schemes=["bcrypt"])`, and the changelog entry cited does
not mention bcrypt anywhere. Recording that plainly, because a security
document asserting a fix that was never written is worse than one
admitting a gap — the gap gets found, the false assurance stops anyone
looking.

The behaviour it was wrong about: bcrypt hashes at most 72 bytes and
ignores the rest, so two different passwords sharing their first 72
bytes produce the same hash and *either* one opens the account.
Password-manager passphrases are exactly the length that runs into this,
and nothing told the user most of what they chose was discarded.

Hashing now uses `bcrypt_sha256` (SHA-256 first, then bcrypt the
fixed-length digest), which removes the ceiling without giving up
bcrypt's slowness. Existing bcrypt hashes still verify and are replaced
on the owner's next successful login — the plaintext is not stored, so
there is no offline migration. Two honest limits: an account nobody logs
into keeps its old hash, and because the rehash uses whatever password
was accepted, an account first accessed with the truncated variant ends
up bound to that variant. Neither widens the hole (reaching either
requires already knowing the first 72 bytes), and both are covered by
tests in `backend/tests/test_password_hashing.py`.

**Decision (v0.1.12): email verification is informational, and is not
enforced.** The v0.1.3 review flagged that `is_verified` was written by
`/auth/verify-email` and then read by nothing — the whole flow was
decorative. That was accurate, and it has been resolved by deciding
deliberately rather than by adding a gate reflexively.

What verification would protect against here, concretely: someone
registering with an address they don't control. This app has no
messaging, no sharing, no public profile and no payments, so such an
account can't be used to reach or impersonate anyone. The one thing the
address governs is password reset — and that cuts the other way, since
the real owner of a mistyped address can use reset to take the account
back. The residual risk is a stranger's inbox receiving one unsolicited
verification email.

Weighed against that, enforcement would have cost: every existing account
has `is_verified = false`, so gating login locks out the entire user base
at once; the verification link expires after 24 hours and there was no
way to obtain another; and blocking a subset of endpoints instead would
mean drawing an arbitrary line and explaining it to users mid-session.

So the finding is closed as *by design*, with two things fixed that were
genuinely wrong regardless of the decision:

- **The status is now visible.** The app sent a verification email at
  registration and never mentioned it again — a user could not tell
  whether they had acted on it or whether it mattered. The progress page
  now says where they stand, in wording that matches this decision (it
  states plainly that everything works without it).
- **There is now a way to act on it** (`POST /auth/resend-verification`,
  authenticated, rate limited per account, retires any outstanding link).
  Showing someone an unverified status with no recourse would have been
  worse than the silence it replaced.

`test_unverified_account_can_use_the_whole_app` pins this: if a
verification gate is added later, that test fails and the choice has to
be made on purpose rather than by drift.

**Finding (Low): registration allows limited account enumeration.**
`/auth/register`'s error message ("Username or email is already
registered") confirms whether a given email already has an account.
This is a genuine trade-off (a clear registration error vs. zero
enumeration surface) rather than an unambiguous bug: someone signing up
has to be told their chosen username is taken, and every alternative —
"check your email either way" — costs a real person a real amount of
confusion to close a leak the attacker can approximate anyway.

**Decided in v0.1.18: kept, deliberately, and now stated as a decision
rather than left as a standing recommendation.** What changed is that
the other two endpoints genuinely close it, so the trade-off is
between "one endpoint tells you" and "no endpoint tells you", not
between one and three.

**Finding (Medium), fixed in v0.1.18: `/auth/login` leaked the same
information by timing.** The paragraph above used to claim login "was
deliberately built to avoid this exact leak". That was true of the
message and false of the clock. `verify_password` ran only when the
username lookup found somebody, and bcrypt is deliberately slow, so a
wrong password for a real account took ~200 ms and a wrong password for
an invented one took ~5 ms — measured at 40x, unmistakable in a single
request without any statistics.

This is the second time this document has asserted a protection that was
not in the code (see A07's bcrypt entry, corrected in v0.1.11), and it
is worth naming the pattern: both claims were true of the part that was
easy to look at and false of the part that wasn't. Fixed with passlib's
`dummy_verify()`, which spends the same hashing work for a username that
does not exist; `tests/test_login_timing.py` measures the result at
1.00x and also asserts the mechanism directly, since a wall-clock
assertion alone is a poor guard on a shared runner.

**Finding (Medium), fixed in v0.1.16: `/auth/request-password-reset`
became an enumeration oracle whenever the mail server was down.** The
endpoint answers identically for known and unknown addresses, which is
the whole reason it exists in that shape — but only the *known* branch
sends mail, and the send was unguarded. So with SMTP refusing
connections, an unregistered address returned 200 and a registered one
returned 500, measured. The control held in every condition except the
one where an attacker would most like it not to.

Recorded as Medium rather than Low because it defeats a control this
document claims, and does so silently: nothing in the app's own
behaviour changes until the day the mail server goes down. Fixed by
handling the failure and logging it instead of propagating it —
`tests/test_email_delivery.py` now asserts that both branches return the
same status *and* the same body with a dead mail server.

## A08: Software and Data Integrity Failures

**Checked:** no `pickle`/`eval`/dynamic code loading, no auto-update
mechanism, no CI/CD pipeline that executes unreviewed third-party scripts.
All request bodies are parsed through Pydantic schemas with defined
types, not deserialized as arbitrary objects.

**Finding:** none identified relative to this app's actual feature set.

## A09: Security Logging and Monitoring Failures

**Fixed this version:** `app/services/security_logging.py` adds
structured logging for registration, login success/failure, rate-limit
hits, refresh-token reuse detection (a strong signal of token theft),
logout, email verification, password reset request/completion, and the
insecure-default-secret-key warning.

**Finding (Medium), fixed in v0.1.7: the log could be forged.** Field
values were written into the line verbatim, and `/auth/login` logs the
username it was given — a value `OAuth2PasswordRequestForm` never
validates for length, charset, or content. A username containing a
newline therefore emitted a *second* log line, composed by the caller: a
backdated, correctly-formatted `login_succeeded user_id=1 username=admin`
is indistinguishable from a real one once written. Everything above in
this section assumes one event per line; a caller who can break that
assumption can make this log say the opposite of what happened, which
defeats the control rather than merely untidying it. Values are now
escaped (and length-capped) before being written — see `_render` in
`app/services/security_logging.py`. Values needing no escaping are still
written bare, so the line format greps were written against is unchanged.

**Honest limitation:** this logs to stdout via Python's standard
`logging` module. There is no log aggregation, alerting, or retention
policy — building one is genuinely infrastructure work (shipping logs to
a platform that can page someone on "50 failed logins for one account in
a minute") that sits outside what application code alone can provide.
This gives you the *events*, in a consistent greppable shape; wiring them
to alerting is a deployment-time concern, tracked as future work rather
than glossed over.

## A10: Server-Side Request Forgery (SSRF)

**Checked:** every outbound network call this app makes — the NLLB model
download (fixed URL from settings, not user-influenced), language
detection and idiom matching (no network calls at all, pure in-process
computation), email sending (destination is the address already on file
for the authenticated/target user, from the database, never a raw URL
fetched based on request input).

**Finding:** not applicable to this app's current feature set. Revisit if
a future feature ever fetches a URL supplied in a request (e.g. importing
content from a link).

---

## For the record: what "done" means here

Every ✅ above reflects specific code reviewed and, where relevant,
specific tests added (`tests/test_security.py`, 56 tests). Every ⚠️ is
either genuinely unresolved and documented as a pre-production requirement
(CORS, default secret), or resolved-for-this-app's-actual-usage-and-explained
rather than hand-waved (the `ecdsa` finding). None of this replaces an
external audit before a real production launch handling real user data —
but it's a real, itemized starting point for one, built the same way the
rest of this project has been: by actually checking, not asserting.
