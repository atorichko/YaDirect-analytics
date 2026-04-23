from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="yadirect-analytics", validation_alias="APP_NAME")
    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")

    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")

    database_url: str = Field(
        default="postgresql+asyncpg://audit:audit@localhost:5433/audit",
        validation_alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://audit:audit@localhost:5433/audit",
        validation_alias="DATABASE_URL_SYNC",
    )

    redis_url: str = Field(default="redis://localhost:6380/0", validation_alias="REDIS_URL")
    celery_broker_url: str = Field(
        default="redis://localhost:6380/1",
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6380/2",
        validation_alias="CELERY_RESULT_BACKEND",
    )

    cors_origins: str = Field(
        default="http://localhost:3000,https://atorichko.asur-adigital.ru",
        validation_alias="CORS_ORIGINS",
    )

    jwt_secret_key: str = Field(
        default="local-dev-secret-change-me-32chars-minimum!!",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_access_expire_minutes: int = Field(default=30, validation_alias="JWT_ACCESS_EXPIRE_MINUTES")
    jwt_refresh_expire_days: int = Field(default=14, validation_alias="JWT_REFRESH_EXPIRE_DAYS")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        return str(v).lower() in {"1", "true", "yes", "on"}

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment.lower() == "production" and len(self.jwt_secret_key) < 32:
            msg = "JWT_SECRET_KEY must be at least 32 characters in production"
            raise ValueError(msg)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
