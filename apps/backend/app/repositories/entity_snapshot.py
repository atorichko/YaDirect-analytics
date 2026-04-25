from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_snapshot import EntitySnapshot, SnapshotEntityType


class EntitySnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_account_and_type(
        self,
        *,
        account_id: UUID,
        entity_type: SnapshotEntityType,
    ) -> list[EntitySnapshot]:
        stmt = (
            select(EntitySnapshot)
            .where(
                EntitySnapshot.account_id == account_id,
                EntitySnapshot.entity_type == entity_type,
            )
            .order_by(EntitySnapshot.entity_key.asc(), EntitySnapshot.captured_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_latest_campaigns(self, *, account_id: UUID) -> list[dict]:
        rows = await self.list_by_account_and_type(account_id=account_id, entity_type=SnapshotEntityType.campaign)
        latest: dict[str, dict] = {}
        for row in rows:
            if row.entity_key in latest:
                continue
            latest[row.entity_key] = row.normalized_snapshot or {}
        return list(latest.values())

    async def list_latest_dicts_for_campaign(
        self,
        *,
        account_id: UUID,
        entity_type: SnapshotEntityType,
        campaign_external_id: str,
    ) -> list[dict]:
        """Latest snapshot per entity_key, restricted to one campaign (avoids loading whole account)."""
        cid = str(campaign_external_id)
        et = entity_type.value
        params = {"aid": str(account_id), "etype": et, "cid": cid}
        if entity_type == SnapshotEntityType.campaign:
            sql = text(
                """
                SELECT DISTINCT ON (entity_key) normalized_snapshot
                FROM entity_snapshots
                WHERE account_id = CAST(:aid AS uuid)
                  AND entity_type = :etype
                  AND COALESCE(normalized_snapshot->>'id', '') = :cid
                ORDER BY entity_key, captured_at DESC
                """
            )
        else:
            sql = text(
                """
                SELECT DISTINCT ON (entity_key) normalized_snapshot
                FROM entity_snapshots
                WHERE account_id = CAST(:aid AS uuid)
                  AND entity_type = :etype
                  AND COALESCE(normalized_snapshot->>'campaign_id', '') = :cid
                ORDER BY entity_key, captured_at DESC
                """
            )
        result = await self._session.execute(sql, params)
        return [m["normalized_snapshot"] or {} for m in result.mappings().all()]

    async def upsert_snapshot(
        self,
        *,
        account_id: UUID,
        entity_type: SnapshotEntityType,
        entity_key: str,
        content_hash: str,
        raw_snapshot: dict,
        normalized_snapshot: dict,
        captured_at: datetime,
    ) -> EntitySnapshot:
        existing = (
            await self._session.execute(
                select(EntitySnapshot).where(
                    EntitySnapshot.account_id == account_id,
                    EntitySnapshot.entity_type == entity_type,
                    EntitySnapshot.entity_key == entity_key,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = EntitySnapshot(
                account_id=account_id,
                entity_type=entity_type,
                entity_key=entity_key,
                content_hash=content_hash,
                raw_snapshot=raw_snapshot,
                normalized_snapshot=normalized_snapshot,
                captured_at=captured_at,
            )
            self._session.add(existing)
        else:
            existing.content_hash = content_hash
            existing.raw_snapshot = raw_snapshot
            existing.normalized_snapshot = normalized_snapshot
            existing.captured_at = captured_at
        await self._session.flush()
        return existing
