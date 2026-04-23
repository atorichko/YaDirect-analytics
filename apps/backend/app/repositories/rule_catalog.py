from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule_catalog import RuleCatalog, RuleDefinition


class RuleCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_version_platform(self, version: str, platform: str) -> RuleCatalog | None:
        stmt = select(RuleCatalog).where(
            RuleCatalog.version == version,
            RuleCatalog.platform == platform,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_catalogs(self, platform: str | None = None) -> list[RuleCatalog]:
        stmt = select(RuleCatalog).order_by(RuleCatalog.created_at.desc())
        if platform:
            stmt = stmt.where(RuleCatalog.platform == platform)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active(self, platform: str) -> RuleCatalog | None:
        stmt = select(RuleCatalog).where(
            RuleCatalog.platform == platform,
            RuleCatalog.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, catalog_id: str) -> RuleCatalog | None:
        result = await self._session.get(RuleCatalog, catalog_id)
        return result

    async def create_catalog(self, catalog: RuleCatalog) -> RuleCatalog:
        self._session.add(catalog)
        await self._session.flush()
        return catalog

    async def create_rules(self, rules: list[RuleDefinition]) -> None:
        self._session.add_all(rules)
        await self._session.flush()

    async def deactivate_platform_catalogs(self, platform: str) -> None:
        stmt = update(RuleCatalog).where(RuleCatalog.platform == platform).values(is_active=False)
        await self._session.execute(stmt)

    async def list_rules(self, catalog_id: str) -> list[RuleDefinition]:
        stmt = select(RuleDefinition).where(RuleDefinition.catalog_id == catalog_id).order_by(RuleDefinition.rule_code)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
