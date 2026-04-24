from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.repositories.finding import FindingRepository
from app.schemas.reporting import FindingDetailOut, FindingOut

router = APIRouter(prefix="/findings", tags=["findings"])


def _to_finding_out(row) -> FindingOut:
    return FindingOut(
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
    return [_to_finding_out(row) for row in rows]


@router.get("/{finding_id}", response_model=FindingDetailOut)
async def get_finding(
    finding_id: UUID,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FindingDetailOut:
    repo = FindingRepository(session)
    row = await repo.get_by_id(finding_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    return FindingDetailOut(
        **_to_finding_out(row).model_dump(),
        audit_id=row.audit_id,
        fingerprint=row.fingerprint,
        ai_verdict=row.ai_verdict,
        updated_at=row.updated_at,
    )


@router.get("/{finding_id}/history", response_model=list[FindingOut])
async def get_finding_history(
    finding_id: UUID,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[FindingOut]:
    repo = FindingRepository(session)
    finding = await repo.get_by_id(finding_id)
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    rows = await repo.list_by_fingerprint(
        account_id=finding.account_id,
        fingerprint=finding.fingerprint,
        limit=limit,
    )
    return [_to_finding_out(row) for row in rows]
