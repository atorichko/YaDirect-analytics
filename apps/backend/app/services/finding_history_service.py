from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.config import settings
from app.models.finding import FindingLevel
from app.models.finding import Finding, FindingStatus
from app.repositories.finding import FindingRepository


class FindingHistoryService:
    def __init__(self, finding_repo: FindingRepository) -> None:
        self._finding_repo = finding_repo

    async def apply_status_lifecycle(
        self,
        *,
        account_id: UUID,
        audit_id: UUID,
        level: FindingLevel | None,
        campaign_external_id: str | None = None,
        current_findings: list[Finding],
        require_ai_verdict_for_previous: bool = False,
    ) -> list[Finding]:
        previous = await self._finding_repo.list_by_account(
            account_id=account_id,
            exclude_audit_id=audit_id,
            level=level,
            campaign_external_id=campaign_external_id,
            require_ai_verdict=True if require_ai_verdict_for_previous else None,
        )
        latest_by_fingerprint: dict[str, Finding] = {}
        for row in previous:
            if row.fingerprint not in latest_by_fingerprint:
                latest_by_fingerprint[row.fingerprint] = row

        fixed_window = timedelta(days=settings.sabotage_reopen_window_days)
        now = datetime.now(timezone.utc)

        current_fingerprints = {item.fingerprint for item in current_findings}
        for finding in current_findings:
            prev = latest_by_fingerprint.get(finding.fingerprint)
            if prev is None:
                finding.status = FindingStatus.new
                finding.suspected_sabotage = False
                continue

            if prev.status == FindingStatus.fixed:
                finding.status = FindingStatus.reopened
                finding.suspected_sabotage = (now - prev.created_at) <= fixed_window
            elif prev.status in {FindingStatus.new, FindingStatus.existing, FindingStatus.reopened}:
                finding.status = FindingStatus.existing
                finding.suspected_sabotage = False
            else:
                finding.status = FindingStatus.new
                finding.suspected_sabotage = False

        fixed_rows: list[Finding] = []
        open_previous = [row for row in latest_by_fingerprint.values() if row.status in {FindingStatus.new, FindingStatus.existing, FindingStatus.reopened}]
        for prev in open_previous:
            if prev.fingerprint in current_fingerprints:
                continue
            fixed_rows.append(
                Finding(
                    audit_id=audit_id,
                    account_id=account_id,
                    campaign_external_id=prev.campaign_external_id,
                    group_external_id=prev.group_external_id,
                    ad_external_id=prev.ad_external_id,
                    rule_code=prev.rule_code,
                    rule_name=prev.rule_name,
                    level=prev.level,
                    severity=prev.severity,
                    entity_key=prev.entity_key,
                    issue_location=prev.issue_location,
                    impact_ru=prev.impact_ru,
                    recommendation_ru=prev.recommendation_ru,
                    evidence=prev.evidence,
                    fingerprint=prev.fingerprint,
                    status=FindingStatus.fixed,
                    suspected_sabotage=False,
                    ai_verdict=prev.ai_verdict,
                )
            )
        return fixed_rows
