from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    redirect = settings.yandex_oauth_redirect_uri.strip()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
        yandex_oauth_redirect_uri=redirect or None,
    )
