from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False, extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    session_secret: str = Field(..., alias="SESSION_SECRET")
    cookie_name: str = Field("chronos_session", alias="COOKIE_NAME")
    cookie_secure: bool = Field(True, alias="COOKIE_SECURE")
    cookie_samesite: str = Field("lax", alias="COOKIE_SAMESITE")
    session_max_age_seconds: int = Field(60 * 60 * 8, alias="SESSION_MAX_AGE_SECONDS")
    log_level: str = Field("info", alias="LOG_LEVEL")

    smtp_enabled: bool = Field(False, alias="SMTP_ENABLED")
    smtp_host: str = Field("localhost", alias="SMTP_HOST")
    smtp_port: int = Field(25, alias="SMTP_PORT")
    smtp_username: str | None = Field(None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(None, alias="SMTP_PASSWORD")
    smtp_from: str = Field("chronos@localhost", alias="SMTP_FROM")
    smtp_use_tls: bool = Field(False, alias="SMTP_USE_TLS")

    public_url: str = Field("http://localhost", alias="PUBLIC_URL")


settings = Settings()
