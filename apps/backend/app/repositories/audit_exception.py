from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_exception import AuditException


class AuditExceptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_account(self, account_id: UUID) -> list[AuditException]:
        result = await self._session.execute(
            select(AuditException)
            .where(AuditException.account_id == account_id)
            .order_by(AuditException.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        account_id: UUID,
        rule_code: str,
        entity_key: str,
        reason: str,
        created_by_user_id: UUID | None,
    ) -> AuditException:
        row = AuditException(
            account_id=account_id,
            rule_code=rule_code,
            entity_key=entity_key,
            reason=reason,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_id(self, exception_id: UUID) -> AuditException | None:
        result = await self._session.execute(select(AuditException).where(AuditException.id == exception_id))
        return result.scalar_one_or_none()

    async def delete(self, row: AuditException) -> None:
        await self._session.delete(row)
