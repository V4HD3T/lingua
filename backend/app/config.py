from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Translation and Language Learning Platform"
    app_version: str = "0.1.10"
    database_url: str = "sqlite:///./app.db"

    secret_key: str = "change-this-for-development"
    algorithm: str = "HS256"
    # Short-lived on purpose: a leaked access token is only useful for this
    # long. Sessions stay alive via refresh tokens (see app/models.py
    # RefreshToken, app/routers/auth.py) rather than by making the access
    # token itself long-lived.
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # How long a just-rotated refresh token keeps working (v0.1.8).
    #
    # Refresh tokens are single-use, and replaying one is treated as
    # theft: it revokes every session the user has. But two browser tabs
    # share one localStorage and refresh independently, so both would
    # present the same token within milliseconds of each other and the
    # second one would destroy a perfectly innocent session. The same
    # happens whenever a response is lost in transit and the client
    # retries.
    #
    # Inside this window, replaying a token that was revoked *by
    # rotation* mints a sibling instead of raising the alarm. Tokens
    # revoked by logout, logout-all, password reset, or reuse detection
    # are never forgiven, whatever the window says.
    #
    # The trade-off, stated plainly: a thief who replays a stolen token
    # within this many seconds of the legitimate client's rotation is
    # not detected. Keep it just long enough to cover a tab race or a
    # retry -- seconds, not minutes.
    refresh_reuse_grace_seconds: int = 10

    # True: mock translation service that runs without downloading a model (default, for dev/testing)
    # False: real NLLB transformer model (requires internet + transformers/torch installed)
    use_mock_translation: bool = True
    translation_model_name: str = "facebook/nllb-200-distilled-600M"

    # SMTP is optional: if smtp_host is empty (the default), the app uses
    # MockEmailService instead of actually sending mail -- see
    # app/services/email_service.py. Fill these in via .env to send real
    # verification/password-reset emails.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "no-reply@lingua.example"

    # Redis translation cache (v0.1.0). Empty = disabled: dev and tests
    # need no Redis running, and the cache degrades gracefully anyway --
    # see app/services/translation_cache.py.
    redis_url: str = ""
    translation_cache_ttl_seconds: int = 604800  # 7 days
    # Bump to invalidate every cached translation at once (e.g. after a
    # model or post-processing change that isn't captured by the backend
    # id below).
    translation_cache_version: int = 1

    # Rate-limit budgets (v0.1.2): configurable so capacity/load testing
    # (see loadtest/) can raise them per-run instead of hacking constants.
    # Defaults unchanged from v0.0.8.
    api_rate_limit_per_minute: int = 120
    translate_rate_limit_per_minute: int = 30

    # Failed logins allowed from one address per minute, across every
    # username it tries (v0.1.6). Successful logins are never charged, so
    # this only ever counts guessing -- which is why it can sit well below
    # the 120/min global backstop without troubling a shared address like
    # an office NAT. Raise it only if a genuinely busy shared address
    # produces enough *failed* logins to trip it.
    login_ip_failure_limit_per_minute: int = 20

    # How many trusted reverse proxies sit in front of this app (v0.1.4).
    #
    # 0 (default): none. The TCP peer address *is* the client -- true for
    # local dev, `docker compose up` (the browser calls :8000 directly),
    # and any direct exposure.
    #
    # N > 0: the rightmost N entries of X-Forwarded-For were appended by
    # proxies you control, so the real client is the Nth entry from the
    # right; everything left of it was written by the client and is
    # ignored. Railway/Render/Fly each put exactly one proxy in front --
    # set this to 1 there (see DEPLOYMENT.md).
    #
    # Why a hop count rather than a trusted-proxy IP allowlist: those
    # platforms' proxy addresses are internal and not documented as
    # stable, so an accurate allowlist can't actually be written. And the
    # thing this replaces -- uvicorn's `--forwarded-allow-ips "*"` -- is
    # worse than either: it trusts the *leftmost* X-Forwarded-For entry,
    # which is entirely client-supplied, so anyone could hand themselves
    # a fresh login/translate/global rate-limit budget on every single
    # request just by varying a header.
    trusted_proxy_hops: int = 0

    # Serve /docs, /redoc and /openapi.json (v0.1.10).
    #
    # Off by default so that forgetting to configure anything is the safe
    # outcome. The schema enumerates every endpoint this app has, the
    # admin API included, with request shapes and validation rules
    # attached -- a map worth handing nobody. Development turns it on
    # explicitly: .env.example (which backend/README.md tells you to copy)
    # and docker-compose.yml both set it, so the documented dev flows are
    # unchanged and only a real deployment has to decide.
    #
    # The alternative -- on by default, deployments opt out -- puts the
    # burden on remembering, which is exactly how v0.1.4's proxy setting
    # went wrong.
    enable_api_docs: bool = False

    frontend_base_url: str = "http://localhost:5173"

    # CORS allowlist, comma-separated. Empty = development defaults (see
    # Settings.cors_origins). Production sets this explicitly and gets
    # exactly what it asks for -- no dev origins leak into a deployment.
    cors_allowed_origins: str = ""


    @property
    def cors_origins(self) -> list[str]:
        """Origins allowed to make browser calls to this API.

        The 127.0.0.1 entry is not redundant: to a browser,
        http://localhost:5173 and http://127.0.0.1:5173 are *different
        origins*, and either spelling is a normal way to reach the Vite
        dev server (Playwright uses the numeric one). Allowing only the
        one broke every cross-origin call from the other -- silently, in
        the browser, which is the worst place to debug it."""
        if self.cors_allowed_origins.strip():
            return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
        return list(
            dict.fromkeys(
                [self.frontend_base_url, "http://localhost:5173", "http://127.0.0.1:5173"]
            )
        )


settings = Settings()
