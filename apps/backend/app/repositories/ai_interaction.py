from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_interaction import AIInteraction


class AIInteractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        audit_id: UUID,
        account_id: UUID,
        rule_code: str,
        entity_key: str,
        provider: str,
        model: str,
        status: str,
        prompt: str,
        response_raw: str | None,
        response_json: dict | None,
        error_message: str | None = None,
        latency_ms: int | None = None,
    ) -> AIInteraction:
        row = AIInteraction(
            audit_id=audit_id,
            account_id=account_id,
            rule_code=rule_code,
            entity_key=entity_key,
            provider=provider,
            model=model,
            status=status,
            prompt=prompt,
            response_raw=response_raw,
            response_json=response_json,
            error_message=error_message,
            latency_ms=latency_ms,
        )
        self._session.add(row)
        await self._session.flush()
        return row
