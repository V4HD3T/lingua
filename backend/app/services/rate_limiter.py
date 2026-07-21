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
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import settings
from app.services.security_logging import log_event


class RateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self._attempts: dict[str, list[datetime]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> bool:
        """Returns True if this request is allowed (and records it as an
        attempt). Returns False if `key` has hit the limit within the
        current window -- the caller should reject the request, typically
        with HTTP 429."""
        now = datetime.now(timezone.utc)
        cutoff = now - self.window
        with self._lock:
            recent = [t for t in self._attempts[key] if t > cutoff]
            if len(recent) >= self.max_attempts:
                self._attempts[key] = recent
                return False
            recent.append(now)
            self._attempts[key] = recent
            return True

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
login_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
register_rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
password_reset_rate_limiter = RateLimiter(max_attempts=3, window_seconds=300)


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


def client_ip(request: Request) -> str:
    """Best-effort per-client key for rate limiting. Behind a reverse
    proxy this is the proxy's address unless forwarded headers are
    configured (a deployment concern, noted for the v0.1.0 deploy guide)."""
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(limiter: RateLimiter, key: str, endpoint: str) -> None:
    """Raises 429 (with a Retry-After hint) when `key` is over budget on
    `limiter`. Lives in the service rather than a router so the response
    shape stays identical everywhere it's used."""
    if not limiter.check(key):
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
