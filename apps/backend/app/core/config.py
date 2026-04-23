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
    celery_broker_url: str = Field(default="redis://localhost:6380/1", validation_alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6380/2", validation_alias="CELERY_RESULT_BACKEND")
    cors_origins: str = Field(
        default="http://localhost:3001,https://atorichko.asur-adigital.ru",
        validation_alias="CORS_ORIGINS",
    )

    jwt_secret_key: str = Field(
        default="local-dev-secret-change-me-32chars-minimum!!",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_access_expire_minutes: int = Field(default=30, validation_alias="JWT_ACCESS_EXPIRE_MINUTES")
    jwt_refresh_expire_days: int = Field(default=14, validation_alias="JWT_REFRESH_EXPIRE_DAYS")
    min_conversions_for_learning: int = Field(default=30, validation_alias="MIN_CONVERSIONS_FOR_LEARNING")
    chronic_budget_limited_days_threshold: int = Field(
        default=3,
        validation_alias="CHRONIC_BUDGET_LIMITED_DAYS_THRESHOLD",
    )
    max_redirect_hops: int = Field(default=5, validation_alias="MAX_REDIRECT_HOPS")
    required_utm_params: str = Field(
        default="utm_source,utm_medium,utm_campaign",
        validation_alias="REQUIRED_UTM_PARAMS",
    )
    polza_ai_base_url: str = Field(default="https://polza.ai/api/v1", validation_alias="POLZA_AI_BASE_URL")
    polza_ai_api_key: str = Field(default="", validation_alias="POLZA_AI_API_KEY")
    ai_model: str = Field(default="gpt-4.1", validation_alias="AI_MODEL")
    yandex_direct_api_url: str = Field(
        default="https://api.direct.yandex.com/json/v5",
        validation_alias="YANDEX_DIRECT_API_URL",
    )
    yandex_oauth_client_id: str = Field(default="", validation_alias="YANDEX_OAUTH_CLIENT_ID")
    yandex_oauth_client_secret: str = Field(default="", validation_alias="YANDEX_OAUTH_CLIENT_SECRET")
    yandex_oauth_redirect_uri: str = Field(default="", validation_alias="YANDEX_OAUTH_REDIRECT_URI")
    sabotage_reopen_window_days: int = Field(default=14, validation_alias="SABOTAGE_REOPEN_WINDOW_DAYS")
    weekly_cron_minute: str = Field(default="0", validation_alias="WEEKLY_CRON_MINUTE")
    weekly_cron_hour: str = Field(default="3", validation_alias="WEEKLY_CRON_HOUR")
    weekly_cron_day_of_week: str = Field(default="1", validation_alias="WEEKLY_CRON_DAY_OF_WEEK")

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def required_utm_params_list(self) -> list[str]:
        return [item.strip() for item in self.required_utm_params.split(",") if item.strip()]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        return str(v).lower() in {"1", "true", "yes", "on"}

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment.lower() == "production" and len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
