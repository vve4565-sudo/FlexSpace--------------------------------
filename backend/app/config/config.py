from datetime import timedelta
from typing import Self

from pydantic import EmailStr, PostgresDsn, computed_field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict, BaseSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: timedelta = timedelta(minutes=60)
    REFRESH_TOKEN_EXPIRE_DAYS: timedelta = timedelta(days=30)

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_TOKEN_LOCATION: list[str] = ["headers"]
    JWT_ACCESS_COOKIE_NAME: str = "access_token"
    JWT_REFRESH_COOKIE_NAME: str = "refresh_token"
    JWT_COOKIE_CSRF_PROTECT: bool = False
    COOKIE_SECURE: bool = True

    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "FlexSpace"

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None
    PUBLIC_BASE_URL: str = "http://localhost:8080"

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = "FlexSpace"
        return self

    @computed_field
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str
    FIRST_SUPERUSER_FULLNAME: str
    FIRST_SUPERUSER_ROLE: str = "admin"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_SSL: bool = False
    API_RATE_LIMIT: int = 120
    LOG_LEVEL: str = "INFO"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if len(value.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 bytes")
        return value


settings = Settings()  # type: ignore
