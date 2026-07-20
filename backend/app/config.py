from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Translation and Language Learning Platform"
    app_version: str = "0.1.0"
    database_url: str = "sqlite:///./app.db"

    secret_key: str = "change-this-for-development"
    algorithm: str = "HS256"
    # Short-lived on purpose: a leaked access token is only useful for this
    # long. Sessions stay alive via refresh tokens (see app/models.py
    # RefreshToken, app/routers/auth.py) rather than by making the access
    # token itself long-lived.
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

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

    frontend_base_url: str = "http://localhost:5173"


settings = Settings()
