from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Translation and Language Learning Platform"
    database_url: str = "sqlite:///./app.db"

    secret_key: str = "change-this-for-development"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # True: mock translation service that runs without downloading the model (default, for dev/testing)
    # False: real NLLB transformer model (requires internet + transformers/torch installation)
    use_mock_translation: bool = True
    translation_model_name: str = "facebook/nllb-200-distilled-600M"


settings = Settings()
