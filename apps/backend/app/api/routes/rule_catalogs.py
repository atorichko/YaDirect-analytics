from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireAdmin, get_db
from app.schemas.rule_catalog import CatalogSummaryOut, CatalogUploadRequest, CatalogWithRulesOut, RuleDefinitionOut
from app.services.rule_catalog_service import RuleCatalogService

router = APIRouter(prefix="/rule-catalogs", tags=["rule-catalogs"])


def _to_detail(catalog, rules) -> CatalogWithRulesOut:
    included_levels = catalog.source_payload.get("included_levels", []) if catalog.source_payload else []
    return CatalogWithRulesOut(
        id=catalog.id,
        version=catalog.version,
        platform=catalog.platform,
        description=catalog.description,
        is_active=catalog.is_active,
        created_at=catalog.created_at,
        included_levels=included_levels,
        source_payload=catalog.source_payload,
        rules=[RuleDefinitionOut.model_validate(r) for r in rules],
    )


@router.post("", response_model=CatalogSummaryOut, status_code=status.HTTP_201_CREATED)
async def upload_catalog(
    body: CatalogUploadRequest,
    admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogSummaryOut:
    service = RuleCatalogService(session)
    try:
        catalog = await service.upload_catalog(body, admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return CatalogSummaryOut.model_validate(catalog)


@router.post("/{catalog_id}/activate", response_model=CatalogSummaryOut)
async def activate_catalog(
    catalog_id: UUID,
    _admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogSummaryOut:
    service = RuleCatalogService(session)
    try:
        catalog = await service.activate_catalog(catalog_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog not found") from None
    return CatalogSummaryOut.model_validate(catalog)


@router.get("", response_model=list[CatalogSummaryOut])
async def list_catalogs(
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    platform: Annotated[str | None, Query()] = None,
) -> list[CatalogSummaryOut]:
    service = RuleCatalogService(session)
    catalogs = await service.list_catalogs(platform)
    return [CatalogSummaryOut.model_validate(c) for c in catalogs]


@router.get("/active", response_model=CatalogWithRulesOut)
async def get_active_catalog(
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    platform: Annotated[str, Query()] = "yandex_direct",
) -> CatalogWithRulesOut:
    service = RuleCatalogService(session)
    result = await service.get_active_with_rules(platform)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active catalog not found")
    catalog, rules = result
    return _to_detail(catalog, rules)


@router.get("/{catalog_id}", response_model=CatalogWithRulesOut)
async def get_catalog_by_id(
    catalog_id: UUID,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogWithRulesOut:
    service = RuleCatalogService(session)
    result = await service.get_catalog_with_rules(catalog_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog not found")
    catalog, rules = result
    return _to_detail(catalog, rules)
