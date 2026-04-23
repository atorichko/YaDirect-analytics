from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.repositories.finding import FindingRepository
from app.schemas.reporting import FindingOut

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=list[FindingOut])
async def list_findings(
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    account_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[FindingOut]:
    repo = FindingRepository(session)
    rows = await repo.list_recent(account_id=account_id, campaign_external_id=campaign_id, limit=limit)
    return [
        FindingOut(
            id=row.id,
            account_id=row.account_id,
            campaign_external_id=row.campaign_external_id,
            group_external_id=row.group_external_id,
            ad_external_id=row.ad_external_id,
            rule_code=row.rule_code,
            rule_name=row.rule_name,
            level=row.level.value,
            severity=row.severity.value,
            issue_location=row.issue_location,
            impact_ru=row.impact_ru,
            recommendation_ru=row.recommendation_ru,
            evidence=row.evidence,
            status=row.status.value,
            suspected_sabotage=row.suspected_sabotage,
            created_at=row.created_at,
        )
        for row in rows
    ]
