"""
Adds standard security-relevant response headers to every response.

This is a defense-in-depth measure -- none of these headers replace
proper input validation or auth checks, but they close off several classes
of browser-side attacks (clickjacking, MIME-sniffing, some XSS vectors)
essentially for free.

CSP here is deliberately conservative (default-src 'self') since this API
doesn't serve HTML/JS itself -- if you later add server-rendered pages or
Swagger UI in production, you'll need to loosen it for /docs specifically
(Swagger UI loads assets from a CDN by default).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.services.rate_limiter import api_rate_limiter, client_ip
from app.services.security_logging import log_event


# The interactive documentation routes. Lives here rather than in main.py
# because this middleware is what has to recognise them, and main.py
# already imports from this module -- putting it the other way round would
# be a cycle.
API_DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})

# Swagger UI and ReDoc are served as a shell page that pulls its script and
# stylesheet from jsdelivr, so `default-src 'self'` blocks the entire page
# from rendering -- which is what had been happening since v0.0.8 added
# these headers: /docs answered 200 and drew nothing. This module's own
# docstring described that as a thing to watch out for "if you later add
# Swagger UI", when it was already there.
#
# Scoped to the documentation routes alone, and only reachable at all when
# ENABLE_API_DOCS is on: the strict policy still covers every route that
# serves data.
#
# 'unsafe-inline' in script-src is not an oversight, and it is not
# optional: FastAPI's docs page boots Swagger with an inline
# `<script>const ui = SwaggerUIBundle({...})</script>`, so without it the
# bundle downloads, defines its global, and then nothing ever mounts --
# verified in a browser, where the page answered 200 and drew an empty
# body. Avoiding it would mean replacing FastAPI's generated HTML with our
# own nonce-stamped copy and then maintaining that bootstrap across
# FastAPI versions, for a page that is off in production and renders no
# user-controlled content -- only a static shell and this app's own
# schema. Accepted here, and nowhere else.
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "worker-src 'self' blob:"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Note: microphone is deliberately NOT denied here. The frontend's
        # speech-recognition features (MicButton, pronunciation practice)
        # need it, and while today the SPA is served from a separate origin
        # (so this header wouldn't reach it), a future single-origin
        # deployment (e.g. FastAPI serving the built frontend from one
        # container) would silently break the mic with a very confusing
        # failure mode if microphone=() were sent.
        response.headers["Permissions-Policy"] = "geolocation=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            _DOCS_CSP
            if settings.enable_api_docs and request.url.path in API_DOCS_PATHS
            else "default-src 'self'"
        )
        # Only meaningful over HTTPS; harmless to send over HTTP (browsers ignore it there).
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


class GeneralRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP request-rate backstop across the whole API (v0.0.8).

    Endpoint-specific limiters (the auth flows, /translate) enforce
    tight, targeted budgets; this is the coarse outer net that stops
    plain request flooding against everything else. /health is exempt
    because deployment platforms poll it aggressively, and a health check
    that can answer 429 reads as an outage.

    Returns JSONResponse directly instead of raising HTTPException:
    exceptions raised inside BaseHTTPMiddleware don't go through
    FastAPI's exception handlers, so a raise here would surface as a 500.
    """

    EXEMPT_PATHS = {"/health"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        key = client_ip(request)
        if not api_rate_limiter.check(key):
            log_event("rate_limit_exceeded", endpoint="global", key=key)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many attempts. Please wait a bit before trying again."},
                headers={"Retry-After": str(int(api_rate_limiter.window.total_seconds()))},
            )
        return await call_next(request)
