from datetime import datetime, timedelta, timezone
import asyncio
from uuid import uuid4

from app.models.finding import Finding, FindingLevel, FindingSeverity, FindingStatus
from app.services.finding_history_service import FindingHistoryService


class _StubFindingRepo:
    def __init__(self, rows: list[Finding]) -> None:
        self._rows = rows

    async def list_by_account(  # noqa: ANN001
        self, account_id, *, exclude_audit_id=None, level=None, campaign_external_id=None
    ):
        return self._rows


def _make_finding(*, status: FindingStatus, fingerprint: str, created_at: datetime) -> Finding:
    row = Finding(
        audit_id=uuid4(),
        account_id=uuid4(),
        campaign_external_id=None,
        group_external_id=None,
        ad_external_id=None,
        rule_code="R",
        rule_name="Rule",
        level=FindingLevel.L1,
        severity=FindingSeverity.high,
        entity_key="e",
        issue_location="loc",
        impact_ru="impact",
        recommendation_ru="rec",
        evidence={},
        fingerprint=fingerprint,
        status=status,
        suspected_sabotage=False,
        ai_verdict=None,
    )
    row.created_at = created_at
    return row


def test_reopened_and_sabotage_flag() -> None:
    now = datetime.now(timezone.utc)
    prev_fixed = _make_finding(status=FindingStatus.fixed, fingerprint="fp1", created_at=now - timedelta(days=1))
    repo = _StubFindingRepo([prev_fixed])
    service = FindingHistoryService(repo)  # type: ignore[arg-type]

    current = _make_finding(status=FindingStatus.new, fingerprint="fp1", created_at=now)
    fixed_rows = asyncio.run(
        service.apply_status_lifecycle(
            account_id=uuid4(), audit_id=uuid4(), level=FindingLevel.L1, current_findings=[current]
        )
    )
    assert current.status == FindingStatus.reopened
    assert current.suspected_sabotage is True
    assert len(fixed_rows) == 0


def test_missing_previous_open_becomes_fixed() -> None:
    now = datetime.now(timezone.utc)
    prev_open = _make_finding(status=FindingStatus.existing, fingerprint="fp-open", created_at=now - timedelta(days=3))
    repo = _StubFindingRepo([prev_open])
    service = FindingHistoryService(repo)  # type: ignore[arg-type]

    fixed_rows = asyncio.run(
        service.apply_status_lifecycle(
            account_id=uuid4(), audit_id=uuid4(), level=FindingLevel.L1, current_findings=[]
        )
    )
    assert len(fixed_rows) == 1
    assert fixed_rows[0].status == FindingStatus.fixed
