from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    app_name: str
    environment: str
    # Non-secret; helps verify which redirect_uri the running process uses for Yandex OAuth.
    yandex_oauth_redirect_uri: str | None = None
