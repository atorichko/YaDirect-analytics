from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule_catalog import RuleCatalog, RuleDefinition
from app.repositories.rule_catalog import RuleCatalogRepository
from app.schemas.rule_catalog import CatalogUploadRequest, PublishBundledCatalogOut
from app.services.rule_catalog_bundle import (
    bump_semver_patch,
    convert_frontend_catalog_to_api_payload,
    load_bundled_rule_catalog_raw,
    resolve_bundled_rule_catalog_path,
)


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
                rule_description=item.rule_description,
                fix_recommendation=item.fix_recommendation,
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

    async def publish_bundled_catalog(
        self,
        *,
        actor_user_id: UUID,
        catalog_version_override: str | None = None,
        activate: bool = True,
    ) -> PublishBundledCatalogOut:
        """Загрузить rule-catalog.json с диска (образ/монорепо), при необходимости активировать."""
        path = resolve_bundled_rule_catalog_path()
        raw = load_bundled_rule_catalog_raw()
        platform = str(raw.get("platform") or "yandex_direct")
        active = await self._repo.get_active(platform)
        active_ver = active.version if active else None

        if catalog_version_override:
            versions_to_try = [catalog_version_override.strip()]
        else:
            file_ver = str(raw.get("catalog_version") or "1.0.0")
            ver = file_ver
            if active_ver and ver == active_ver:
                ver = bump_semver_patch(ver)
            versions_to_try = []
            cur = ver
            for _ in range(48):
                versions_to_try.append(cur)
                cur = bump_semver_patch(cur)

        catalog: RuleCatalog | None = None
        used_ver: str | None = None
        for ver_try in versions_to_try:
            body = convert_frontend_catalog_to_api_payload(raw, ver_try)
            payload = CatalogUploadRequest.model_validate(body)
            try:
                catalog = await self.upload_catalog(payload, actor_user_id)
                used_ver = ver_try
                break
            except ValueError:
                continue

        if catalog is None or used_ver is None:
            msg = "Could not allocate a new catalog version (all candidates exist). Pass catalog_version explicitly."
            raise ValueError(msg)

        activated = False
        if activate:
            catalog = await self.activate_catalog(catalog.id)
            activated = True

        return PublishBundledCatalogOut(
            catalog_version_used=used_ver,
            catalog_id=catalog.id,
            activated=activated,
            bundle_path=str(path),
        )
