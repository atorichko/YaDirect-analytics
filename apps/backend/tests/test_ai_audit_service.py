import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.models.finding import Finding, FindingLevel, FindingSeverity, FindingStatus
from app.services.ai_audit_service import AIAuditService


def _mk_finding(*, rule_code: str, entity_key: str, status: FindingStatus, ai_verdict: dict | None) -> Finding:
    row = Finding(
        audit_id=uuid4(),
        account_id=uuid4(),
        campaign_external_id="C200",
        group_external_id=None,
        ad_external_id=None,
        rule_code=rule_code,
        rule_name=rule_code,
        level=FindingLevel.L3,
        severity=FindingSeverity.high,
        entity_key=entity_key,
        issue_location=entity_key,
        impact_ru="impact",
        recommendation_ru="rec",
        evidence={},
        fingerprint=f"{rule_code}:{entity_key}",
        status=status,
        suspected_sabotage=False,
        ai_verdict=ai_verdict,
    )
    row.created_at = datetime.now(timezone.utc)
    return row


class _RepoStub:
    def __init__(self, previous: list[Finding]) -> None:
        self._previous = previous

    async def list_by_account(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return list(self._previous)


def test_ai_cannot_close_when_deterministic_open_exists() -> None:
    service = AIAuditService.__new__(AIAuditService)
    fixed_ai = _mk_finding(
        rule_code="MISSING_REQUIRED_UTM",
        entity_key="ad:A1:ad.url:missing_utm",
        status=FindingStatus.fixed,
        ai_verdict={"v": 1},
    )
    prev_det_open = _mk_finding(
        rule_code="MISSING_REQUIRED_UTM",
        entity_key="ad:A1:ad.url:missing_utm",
        status=FindingStatus.new,
        ai_verdict=None,
    )
    service._findings = _RepoStub([prev_det_open])

    result = asyncio.run(
        service._drop_fixed_rows_shadowed_by_deterministic(
            account_id=uuid4(),
            audit_id=uuid4(),
            campaign_external_id="C200",
            fixed_rows=[fixed_ai],
        )
    )
    assert result == []


def test_ai_can_close_when_only_ai_history_exists() -> None:
    service = AIAuditService.__new__(AIAuditService)
    fixed_ai = _mk_finding(
        rule_code="MISSING_REQUIRED_UTM",
        entity_key="ad:A1:ad.url:missing_utm",
        status=FindingStatus.fixed,
        ai_verdict={"v": 1},
    )
    prev_ai_open = _mk_finding(
        rule_code="MISSING_REQUIRED_UTM",
        entity_key="ad:A1:ad.url:missing_utm",
        status=FindingStatus.new,
        ai_verdict={"v": 1},
    )
    service._findings = _RepoStub([prev_ai_open])

    result = asyncio.run(
        service._drop_fixed_rows_shadowed_by_deterministic(
            account_id=uuid4(),
            audit_id=uuid4(),
            campaign_external_id="C200",
            fixed_rows=[fixed_ai],
        )
    )
    assert len(result) == 1
