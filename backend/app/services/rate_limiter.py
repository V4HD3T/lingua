"""
A small in-memory sliding-window rate limiter, applied to the
authentication endpoints as brute-force protection.

Honest about its limits: this is in-process memory, so it resets on
restart and does **not** share state across multiple worker processes or
horizontally-scaled instances. That's a real gap for a production
multi-instance deployment -- there you'd want a shared store (Redis is
the standard choice) so all instances see the same attempt counts. For a
single-process deployment (which is what this project runs as), it's a
real, working protection with no extra infrastructure required.

Hand-rolled rather than pulling in a rate-limiting library: the mechanism
is simple enough to implement correctly in a few lines, and understanding
exactly how your own brute-force protection works matters more here than
saving a dozen lines of code.

Memory (v0.1.5): attempt history is swept once per window, so what the
table holds is bounded by the number of *distinct keys seen within one
window* rather than by every key seen since the process started. That
bound is still a function of incoming traffic, not a constant -- a burst
of requests from many addresses inside a single window is held until that
window turns over. Bounding it harder would mean evicting live entries,
which is the one thing a rate limiter must not do (see
RateLimiter._sweep). Making it genuinely constant, and shared across
instances, is the same Redis-backed answer as the multi-instance gap
above.
"""

import ipaddress
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from fastapi import HTTPException, Request, status

from app.config import settings
from app.services.security_logging import log_event


class RateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self._attempts: dict[str, list[datetime]] = defaultdict(list)
        self._lock = Lock()
        # First sweep is a window away: there is nothing to collect yet.
        self._next_sweep = datetime.now(timezone.utc) + self.window

    def check(self, key: str) -> bool:
        """Returns True if this request is allowed (and records it as an
        attempt). Returns False if `key` has hit the limit within the
        current window -- the caller should reject the request, typically
        with HTTP 429."""
        now = datetime.now(timezone.utc)
        cutoff = now - self.window
        with self._lock:
            if now >= self._next_sweep:
                self._sweep(cutoff)
                self._next_sweep = now + self.window
            recent = [t for t in self._attempts[key] if t > cutoff]
            if len(recent) >= self.max_attempts:
                self._attempts[key] = recent
                return False
            recent.append(now)
            self._attempts[key] = recent
            return True

    def _sweep(self, cutoff: datetime) -> None:
        """Drops keys whose attempts have all aged out of the window.
        Caller must hold the lock (v0.1.5).

        Without this, `_attempts` only ever grew: `check()` prunes the
        timestamps of the key it was asked about, but every key ever seen
        kept its dict entry forever -- including entries pruned down to an
        empty list. One process-lifetime of traffic therefore leaked one
        entry per distinct client address, and an attacker rotating
        addresses (trivial from any IPv6 allocation, which hands out more
        than there are addresses in all of IPv4) could grow it until the
        process died.

        This is safe to do *because* it only removes keys that are already
        spent: a key survives here only if it still has an attempt inside
        the window. Re-checking a swept key computes `recent = []` and
        allows the request -- exactly what it would have computed from the
        expired timestamps had they been left in place. So the sweep
        changes memory, never a limiting decision, and in particular can
        never hand a currently-throttled caller a fresh budget.

        That last property is why this isn't a size cap. An LRU-style
        "keep the newest N keys" bound would evict *live* entries under
        pressure, which is precisely the state an attacker generating keys
        is in -- they could push their own throttled entry out and start
        over. Collecting only expired entries has no such failure mode.

        Cost: one pass over the table, holding the lock, at most once per
        window. Checking `times[-1]` is O(1) per key because attempts are
        appended in order, so the newest is last -- a sweep is O(keys),
        not O(attempts). A table bloated to a million keys is a single
        pause of some tens of milliseconds, after which it is small again.
        """
        stale = [
            key for key, times in self._attempts.items() if not times or times[-1] <= cutoff
        ]
        for key in stale:
            del self._attempts[key]

    @property
    def tracked_keys(self) -> int:
        """How many keys currently hold attempt history. Exposed for tests
        and for anyone wanting to sanity-check memory use in a running
        process."""
        with self._lock:
            return len(self._attempts)

    def is_exhausted(self, key: str) -> bool:
        """True if `key` is out of budget, **without** recording an
        attempt (v0.1.6).

        The pair to `record()`: together they express "only some outcomes
        count against this budget", which `check()` can't, since it always
        records. The login flow uses them to charge an IP for failed
        logins only -- see app/routers/auth.py.

        Reads with .get() rather than indexing so that merely asking the
        question doesn't create a table entry for an unseen key.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - self.window
        with self._lock:
            recent = [t for t in self._attempts.get(key, []) if t > cutoff]
            return len(recent) >= self.max_attempts

    def record(self, key: str) -> None:
        """Records an attempt against `key` without testing the budget.
        See is_exhausted()."""
        now = datetime.now(timezone.utc)
        cutoff = now - self.window
        with self._lock:
            recent = [t for t in self._attempts[key] if t > cutoff]
            recent.append(now)
            self._attempts[key] = recent

    def reset(self, key: str) -> None:
        """Clears attempts for `key` -- e.g. call this on a successful
        login so a legitimate user who mistyped their password a couple
        of times isn't left sitting close to the limit."""
        with self._lock:
            self._attempts.pop(key, None)

    def clear_all(self) -> None:
        """Wipes every key's attempt history. Not used by the app itself --
        this exists so tests can reset shared limiter state between test
        cases (see tests/conftest.py), since these limiters are
        module-level singletons and Starlette's TestClient always reports
        the same fake client IP."""
        with self._lock:
            self._attempts.clear()


# Separate limiter instances so login attempts and registration attempts
# don't share a budget -- a burst of signups shouldn't lock out login, or
# vice versa.
#
# login_rate_limiter is keyed per (address, username) as of v0.1.6, not
# per address -- see login_key() below and the two-budget note under
# login_ip_rate_limiter.
login_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
register_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
password_reset_rate_limiter = RateLimiter(max_attempts=3, window_seconds=300)

# Resending a verification email (v0.1.12). Keyed by user id rather than
# address: the endpoint requires a session, so the account is the thing
# worth bounding, and keying by address would let one person behind a
# shared connection use up everyone else's budget.
verification_resend_rate_limiter = RateLimiter(max_attempts=3, window_seconds=900)

# Failed logins from one address, across every username it tries (v0.1.6).
#
# This exists because of what fixing the reset bypass opened up. Keying
# the budget above per (address, username) is what stops a successful
# login from clearing an unrelated account's failures -- but on its own it
# would also mean one address gets 5 guesses *per username*, i.e. no cap
# at all on password spraying (one common password against thousands of
# accounts). The two budgets answer different attacks and are both needed:
# the pair budget bounds how hard one account can be hammered, this one
# bounds how much guessing one address can do in total.
#
# Only *failures* are charged here, and it is never reset. That's what
# keeps it safe to set tight: people logging in successfully never touch
# it, so a shared address -- office NAT, mobile CGNAT, a household --
# doesn't accumulate a budget just by being busy. The global backstop in
# GeneralRateLimitMiddleware (120/min) is the only other thing standing
# between spraying and the password hashes, and 120 guesses a minute is
# not a limit worth relying on.
login_ip_rate_limiter = RateLimiter(
    max_attempts=settings.login_ip_failure_limit_per_minute, window_seconds=60
)


def login_key(ip: str, username: str) -> str:
    """Rate-limit key for one account being tried from one address
    (v0.1.6).

    Before this, login was limited per address alone, and a successful
    login reset that address's whole budget. An attacker with any account
    of their own could therefore spend four guesses on a victim, log in as
    themselves to zero the counter, and repeat -- turning a 5/min limit
    into roughly the global backstop's 120/min. Keying on the pair means
    logging in as yourself clears only your own pair.

    The username is case-folded so that varying capitalisation can't mint
    fresh budgets. Today's lookup is case-sensitive, so "Victim" simply
    finds no user -- but `=` on text is case-*insensitive* under some
    collations (MySQL's default, Postgres with citext), and DEPLOYMENT.md
    already points at Postgres. Folding costs nothing and removes the
    dependency on that staying true. Two distinct usernames folding
    together is harmless: they share a budget, which over-limits rather
    than under-limits.

    NUL separates the parts because a username can contain anything --
    login takes it straight off an OAuth2 form with no validation -- and
    an ordinary separator like ":" would let one pair's key collide with
    another's.
    """
    return f"{ip}\x00{username.casefold()}"


# --- Shared enforcement + app-wide limiters (v0.0.8) -------------------------
#
# v0.0.7 introduced per-endpoint limiters for the auth flows, enforced by a
# private helper inside the auth router. v0.0.8 generalises that: the
# HTTP-shaped part of enforcement (429 + Retry-After) lives here so any
# router can rate-limit an endpoint in one line, and two new limiters cover
# the rest of the API -- a per-IP backstop across all endpoints (enforced
# by GeneralRateLimitMiddleware in app/middleware.py) and a tighter budget
# for /translate, the endpoint that will eventually run real model
# inference and is therefore the most expensive thing an abuser can call.


def _parse_forwarded_host(value: str) -> Optional[str]:
    """Extracts a bare IP address from a single X-Forwarded-For entry.

    Entries are usually bare addresses, but a proxy may append the source
    port ("1.2.3.4:51234", "[2001:db8::1]:443"). Returns None for
    anything that doesn't parse as an IP address -- see client_ip() for
    why refusing to guess matters here.

    Returning the *parsed* address rather than the original string also
    normalizes it, which stops one client from occupying many rate-limit
    buckets just by respelling its own IPv6 address ("::1" and
    "0:0:0:0:0:0:0:1" are the same host and must map to the same key).
    """
    value = value.strip()
    if not value:
        return None

    if value.startswith("["):
        # Bracketed IPv6, with or without a trailing ":port".
        end = value.find("]")
        if end == -1:
            return None
        candidate = value[1:end]
    elif value.count(":") == 1:
        # Exactly one colon means IPv4 with a port; a bare IPv6 address
        # always has more, and never carries a port unbracketed.
        candidate = value.rsplit(":", 1)[0]
    else:
        candidate = value

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    """Per-client key for rate limiting and security logging.

    Resolved here rather than by uvicorn's --proxy-headers (v0.1.4).
    That flag was previously passed as `--forwarded-allow-ips "*"`, which
    makes uvicorn rewrite `request.client` from the **leftmost**
    X-Forwarded-For entry -- the one furthest from the proxy and written
    entirely by whoever sent the request. Every per-IP budget in this
    module (login 5/min, register, password reset, /translate, and the
    app-wide backstop) was therefore bypassable by putting a different
    random address in a header on each request, and the `ip=` field in
    the security log was attacker-authored.

    The correct entry is counted from the *right*: each proxy appends the
    address of its own immediate peer, so with `trusted_proxy_hops`
    proxies in front, the last one to write was the outermost and the
    real client sits `trusted_proxy_hops` from the end. Anything to the
    left of it arrived with the request and is ignored.

    Falls back to the TCP peer address whenever the header can't be
    trusted to mean what the configuration claims -- an unparseable entry,
    or a chain shorter than the configured hop count (which means the
    request did not come through the expected proxies). That fallback
    lumps such requests together under the proxy's own address, i.e. it
    over-limits rather than under-limits: the safe direction for a
    misconfiguration to fail in.
    """
    peer = request.client.host if request.client else "unknown"

    hops = settings.trusted_proxy_hops
    if hops <= 0:
        return peer

    # A request can carry several X-Forwarded-For headers; together they
    # form one chain, in order.
    chain = [
        entry
        for header in request.headers.getlist("x-forwarded-for")
        for entry in header.split(",")
    ]
    if len(chain) < hops:
        return peer

    return _parse_forwarded_host(chain[-hops]) or peer


def enforce_rate_limit(
    limiter: RateLimiter, key: str, endpoint: str, *, record: bool = True
) -> None:
    """Raises 429 (with a Retry-After hint) when `key` is over budget on
    `limiter`. Lives in the service rather than a router so the response
    shape stays identical everywhere it's used.

    `record=False` tests the budget without spending from it, for callers
    that decide afterwards whether this attempt counts -- the login flow
    charges its per-address budget only for failures (v0.1.6). Those
    callers are responsible for calling limiter.record() themselves.
    """
    over_budget = limiter.is_exhausted(key) if not record else not limiter.check(key)
    if over_budget:
        log_event("rate_limit_exceeded", endpoint=endpoint, key=key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a bit before trying again.",
            headers={"Retry-After": str(int(limiter.window.total_seconds()))},
        )


# The backstop default is deliberately generous (120/min ≈ 2 requests/
# second sustained): it should never bother a real person clicking around,
# only scripts hammering the API. Budgets come from settings as of v0.1.2
# so a capacity test can raise them per-run (API_RATE_LIMIT_PER_MINUTE /
# TRANSLATE_RATE_LIMIT_PER_MINUTE env vars) -- with defaults, a single-IP
# load generator correctly slams into the limiter instead of measuring it.
api_rate_limiter = RateLimiter(
    max_attempts=settings.api_rate_limit_per_minute, window_seconds=60
)
translate_rate_limiter = RateLimiter(
    max_attempts=settings.translate_rate_limit_per_minute, window_seconds=60
)
