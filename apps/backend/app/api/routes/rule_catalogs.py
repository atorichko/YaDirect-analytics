from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireAdmin, get_db
from app.schemas.rule_catalog import (
    CatalogSummaryOut,
    CatalogUploadRequest,
    CatalogWithRulesOut,
    PublishBundledCatalogBody,
    PublishBundledCatalogOut,
    RuleDefinitionOut,
)
from app.core.ai_prompt_defaults import AI_RULE_APPENDIX_RU
from app.services.l1_rules import build_l1_rule_registry
from app.services.l2_rules import build_l2_rule_registry
from app.services.l3_rules import build_l3_rule_registry
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
        updated_at=catalog.updated_at,
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


@router.post("/publish-bundled", response_model=PublishBundledCatalogOut, status_code=status.HTTP_201_CREATED)
async def publish_bundled_catalog(
    admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: PublishBundledCatalogBody,
) -> PublishBundledCatalogOut:
    """Опубликовать rule-catalog.json с диска сервера (образ/путь) и при необходимости активировать (удобно из UI)."""
    service = RuleCatalogService(session)
    try:
        return await service.publish_bundled_catalog(
            actor_user_id=admin.id,
            catalog_version_override=body.catalog_version,
            activate=body.activate,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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


@router.get("/active/coverage")
async def get_active_catalog_coverage(
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    platform: Annotated[str, Query()] = "yandex_direct",
) -> dict:
    service = RuleCatalogService(session)
    result = await service.get_active_with_rules(platform)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active catalog not found")
    catalog, rules = result
    implemented = {
        "L1": set(build_l1_rule_registry().keys()),
        "L2": set(build_l2_rule_registry().keys()),
        "L3": set(build_l3_rule_registry().keys()),
    }
    rows = []
    missing = []
    for rule in rules:
        lvl = str(rule.level)
        is_implemented = True if rule.check_type == "ai_assisted" else rule.rule_code in implemented.get(lvl, set())
        row = {
            "rule_code": rule.rule_code,
            "level": lvl,
            "check_type": rule.check_type,
            "enabled": rule.enabled,
            "implemented": is_implemented,
        }
        rows.append(row)
        if rule.enabled and not is_implemented:
            missing.append(rule.rule_code)
    return {
        "catalog_version": catalog.version,
        "catalog_updated_at": catalog.updated_at.isoformat(),
        "ai_appendix_rule_codes": sorted(AI_RULE_APPENDIX_RU.keys()),
        "total_rules": len(rows),
        "enabled_rules": len([r for r in rows if r["enabled"]]),
        "implemented_enabled_rules": len([r for r in rows if r["enabled"] and r["implemented"]]),
        "missing_enabled_rules": sorted(missing),
        "rules": rows,
    }
