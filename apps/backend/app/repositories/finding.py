from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import FindingLevel
from app.models.finding import Finding


class FindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(self, findings: list[Finding]) -> None:
        if not findings:
            return
        self._session.add_all(findings)
        await self._session.flush()

    async def list_by_account(
        self,
        account_id: UUID,
        *,
        exclude_audit_id: UUID | None = None,
        level: FindingLevel | None = None,
        campaign_external_id: str | None = None,
        require_ai_verdict: bool | None = None,
        rule_codes: set[str] | None = None,
    ) -> list[Finding]:
        if rule_codes is not None and not rule_codes:
            return []
        stmt = select(Finding).where(Finding.account_id == account_id).order_by(Finding.created_at.desc())
        if exclude_audit_id:
            stmt = stmt.where(Finding.audit_id != exclude_audit_id)
        if level is not None:
            stmt = stmt.where(Finding.level == level)
        if campaign_external_id is not None:
            stmt = stmt.where(Finding.campaign_external_id == campaign_external_id)
        if require_ai_verdict is True:
            stmt = stmt.where(Finding.ai_verdict.isnot(None))
        elif require_ai_verdict is False:
            stmt = stmt.where(Finding.ai_verdict.is_(None))
        if rule_codes:
            stmt = stmt.where(Finding.rule_code.in_(sorted(rule_codes)))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent(
        self,
        *,
        account_id: UUID | None = None,
        campaign_external_id: str | None = None,
        limit: int = 200,
    ) -> list[Finding]:
        stmt = select(Finding).order_by(Finding.created_at.desc()).limit(limit)
        if account_id is not None:
            stmt = stmt.where(Finding.account_id == account_id)
        if campaign_external_id:
            stmt = stmt.where(
                or_(
                    Finding.campaign_external_id == campaign_external_id,
                    Finding.evidence["scope"].astext == "account",
                )
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, finding_id: UUID) -> Finding | None:
        result = await self._session.execute(select(Finding).where(Finding.id == finding_id))
        return result.scalar_one_or_none()

    async def list_by_fingerprint(
        self,
        *,
        account_id: UUID,
        fingerprint: str,
        limit: int = 200,
    ) -> list[Finding]:
        stmt = (
            select(Finding)
            .where(Finding.account_id == account_id, Finding.fingerprint == fingerprint)
            .order_by(Finding.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
