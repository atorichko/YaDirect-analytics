from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_log import ActionLog


class ActionLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        action: str,
        entity_type: str,
        entity_key: str,
        payload: dict,
        account_id: UUID | None = None,
        actor_user_id: UUID | None = None,
    ) -> ActionLog:
        row = ActionLog(
            action=action,
            entity_type=entity_type,
            entity_key=entity_key,
            payload=payload,
            account_id=account_id,
            actor_user_id=actor_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row
