from fastapi import APIRouter

from app.api.routes import ad_accounts, auth, exceptions, findings, health, rule_catalogs, settings, users
from app.api.routes.audits import router as audits_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(rule_catalogs.router)
api_router.include_router(settings.router)
api_router.include_router(audits_router)
api_router.include_router(ad_accounts.router)
api_router.include_router(findings.router)
api_router.include_router(exceptions.router)
