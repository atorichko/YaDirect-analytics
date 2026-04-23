from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule_catalog import RuleCatalog, RuleDefinition
from app.repositories.rule_catalog import RuleCatalogRepository
from app.schemas.rule_catalog import CatalogUploadRequest


class RuleCatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RuleCatalogRepository(session)

    async def upload_catalog(self, payload: CatalogUploadRequest, actor_user_id: UUID | None) -> RuleCatalog:
        existing = await self._repo.get_by_version_platform(payload.catalog_version, payload.platform)
        if existing is not None:
            msg = "Catalog version already exists for platform"
            raise ValueError(msg)

        catalog = RuleCatalog(
            version=payload.catalog_version,
            platform=payload.platform,
            description=payload.description,
            is_active=False,
            source_payload=payload.model_dump(),
            created_by_user_id=actor_user_id,
        )
        catalog = await self._repo.create_catalog(catalog)

        rules = [
            RuleDefinition(
                catalog_id=catalog.id,
                rule_code=item.rule_code,
                rule_name=item.rule_name,
                level=item.level,
                severity=item.severity,
                check_type=item.check_type,
                enabled=item.enabled,
                config=item.config,
            )
            for item in payload.rules
        ]
        if rules:
            await self._repo.create_rules(rules)
        await self._session.commit()
        return catalog

    async def activate_catalog(self, catalog_id: UUID) -> RuleCatalog:
        catalog = await self._repo.get_by_id(str(catalog_id))
        if catalog is None:
            msg = "Catalog not found"
            raise LookupError(msg)
        await self._repo.deactivate_platform_catalogs(catalog.platform)
        catalog.is_active = True
        await self._session.commit()
        await self._session.refresh(catalog)
        return catalog

    async def get_active_with_rules(self, platform: str) -> tuple[RuleCatalog, list[RuleDefinition]] | None:
        catalog = await self._repo.get_active(platform)
        if catalog is None:
            return None
        rules = await self._repo.list_rules(str(catalog.id))
        return catalog, rules

    async def list_catalogs(self, platform: str | None) -> list[RuleCatalog]:
        return await self._repo.list_catalogs(platform)

    async def get_catalog_with_rules(self, catalog_id: UUID) -> tuple[RuleCatalog, list[RuleDefinition]] | None:
        catalog = await self._repo.get_by_id(str(catalog_id))
        if catalog is None:
            return None
        rules = await self._repo.list_rules(str(catalog.id))
        return catalog, rules
