from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_credential import AccountCredential


class AccountCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_account_id(self, account_id: UUID) -> AccountCredential | None:
        result = await self._session.execute(
            select(AccountCredential).where(AccountCredential.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        account_id: UUID,
        access_token: str,
        refresh_token: str | None,
        token_expires_at: datetime | None,
    ) -> AccountCredential:
        row = await self.get_by_account_id(account_id)
        if row is None:
            row = AccountCredential(
                account_id=account_id,
                provider="yandex_direct",
                access_token_encrypted=access_token,
                refresh_token_encrypted=refresh_token,
                token_expires_at=token_expires_at,
            )
            self._session.add(row)
        else:
            row.access_token_encrypted = access_token
            row.refresh_token_encrypted = refresh_token
            row.token_expires_at = token_expires_at
        await self._session.flush()
        return row
