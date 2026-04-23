from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ad_account import AdAccount
from app.models.audit import Audit


class AdAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, account_id: UUID) -> AdAccount | None:
        result = await self._session.execute(select(AdAccount).where(AdAccount.id == account_id))
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> AdAccount | None:
        result = await self._session.execute(select(AdAccount).where(AdAccount.external_id == external_id))
        return result.scalar_one_or_none()

    async def get_by_login(self, login: str) -> AdAccount | None:
        result = await self._session.execute(select(AdAccount).where(AdAccount.login == login))
        return result.scalar_one_or_none()

    async def list_active_ids(self) -> list[UUID]:
        result = await self._session.execute(select(AdAccount.id).where(AdAccount.is_active.is_(True)))
        return list(result.scalars().all())

    async def list_all(self) -> list[AdAccount]:
        result = await self._session.execute(select(AdAccount).order_by(AdAccount.name.asc()))
        return list(result.scalars().all())

    async def list_with_last_audit(self) -> list[tuple[AdAccount, datetime | None]]:
        latest_subq = (
            select(
                Audit.account_id.label("account_id"),
                func.max(Audit.finished_at).label("last_audit_at"),
            )
            .group_by(Audit.account_id)
            .subquery()
        )
        result = await self._session.execute(
            select(AdAccount, latest_subq.c.last_audit_at)
            .outerjoin(latest_subq, latest_subq.c.account_id == AdAccount.id)
            .order_by(AdAccount.name.asc())
        )
        return list(result.all())

    async def delete(self, account: AdAccount) -> None:
        await self._session.delete(account)

    async def create(
        self,
        *,
        external_id: str,
        name: str,
        login: str,
        platform: str = "yandex_direct",
        timezone: str = "Europe/Moscow",
    ) -> AdAccount:
        row = AdAccount(
            external_id=external_id,
            name=name,
            login=login,
            platform=platform,
            timezone=timezone,
            is_active=True,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row
