from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Audit, AuditStatus, AuditTrigger


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        account_id: UUID,
        trigger: AuditTrigger,
        catalog_version: str,
        initiated_by_user_id: UUID | None,
    ) -> Audit:
        row = Audit(
            account_id=account_id,
            trigger=trigger,
            status=AuditStatus.queued,
            catalog_version=catalog_version,
            initiated_by_user_id=initiated_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def mark_running(self, audit: Audit, started_at: datetime) -> None:
        audit.status = AuditStatus.running
        audit.started_at = started_at
        await self._session.flush()

    async def mark_completed(self, audit: Audit, finished_at: datetime) -> None:
        audit.status = AuditStatus.completed
        audit.finished_at = finished_at
        await self._session.flush()

    async def mark_failed(self, audit: Audit, finished_at: datetime) -> None:
        audit.status = AuditStatus.failed
        audit.finished_at = finished_at
        await self._session.flush()
