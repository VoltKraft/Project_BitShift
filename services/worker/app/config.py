from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    job_poll_interval_seconds: float = Field(5.0, alias="JOB_POLL_INTERVAL_SECONDS")
    log_level: str = Field("info", alias="LOG_LEVEL")

    max_substitution_batch: int = Field(20, alias="MAX_SUBSTITUTION_BATCH")
    fallback_notification_to: str | None = Field(default=None, alias="FALLBACK_NOTIFICATION_TO")

    smtp_enabled: bool = Field(False, alias="SMTP_ENABLED")
    smtp_host: str = Field("localhost", alias="SMTP_HOST")
    smtp_port: int = Field(25, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: str = Field("chronos@example.org", alias="SMTP_FROM")
    smtp_use_tls: bool = Field(False, alias="SMTP_USE_TLS")


settings = Settings()
