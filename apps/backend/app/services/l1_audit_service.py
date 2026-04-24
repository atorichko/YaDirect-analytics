from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditTrigger
from app.models.entity_snapshot import EntitySnapshot, SnapshotEntityType
from app.models.finding import Finding, FindingLevel, FindingSeverity, FindingStatus
from app.repositories.action_log import ActionLogRepository
from app.repositories.ad_account import AdAccountRepository
from app.repositories.audit import AuditRepository
from app.repositories.entity_snapshot import EntitySnapshotRepository
from app.repositories.finding import FindingRepository
from app.repositories.rule_catalog import RuleCatalogRepository
from app.schemas.audit import RunL1AuditResponse
from app.services.fingerprint_utils import evidence_signature
from app.services.finding_history_service import FindingHistoryService
from app.services.l1_rules import L1Context, _is_active_yandex_campaign, build_l1_rule_registry


def _is_active_state(value: object) -> bool:
    return str(value or "").lower() in {"active", "on", "enabled"}


class L1AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._accounts = AdAccountRepository(session)
        self._audits = AuditRepository(session)
        self._snapshots = EntitySnapshotRepository(session)
        self._findings = FindingRepository(session)
        self._history = FindingHistoryService(self._findings)
        self._logs = ActionLogRepository(session)
        self._catalog_repo = RuleCatalogRepository(session)
        self._registry = build_l1_rule_registry()

    async def run_manual_l1_audit(
        self,
        *,
        account_id: UUID,
        actor_user_id: UUID | None,
        campaign_external_id: str | None = None,
    ) -> RunL1AuditResponse:
        account = await self._accounts.get_by_id(account_id)
        if account is None:
            raise LookupError("Ad account not found")

        active_catalog = await self._catalog_repo.get_active("yandex_direct")
        if active_catalog is None:
            raise LookupError("Active rule catalog not found")
        rules = await self._catalog_repo.list_rules(str(active_catalog.id))
        l1_rules = [r for r in rules if r.enabled and r.level == "L1" and r.check_type == "deterministic"]

        audit = await self._audits.create(
            account_id=account_id,
            trigger=AuditTrigger.manual,
            catalog_version=active_catalog.version,
            initiated_by_user_id=actor_user_id,
        )
        started_at = datetime.now(timezone.utc)
        await self._audits.mark_running(audit, started_at)
        await self._session.flush()

        try:
            context = await self._build_context(account_id, campaign_external_id=campaign_external_id)
            findings_rows: list[Finding] = []
            for rule in l1_rules:
                handler = self._registry.get(rule.rule_code)
                if handler is None:
                    continue
                raw_rule = dict(rule.config or {})
                raw_rule["recommendation_ru"] = raw_rule.get("recommendation_ru") or rule.rule_name
                drafts = handler(context, raw_rule)
                for draft in drafts:
                    signature = evidence_signature(draft.evidence)
                    fingerprint = self._fingerprint(rule.rule_code, draft.entity_key, signature)
                    findings_rows.append(
                        Finding(
                            audit_id=audit.id,
                            account_id=account_id,
                            campaign_external_id=draft.campaign_external_id,
                            group_external_id=draft.group_external_id,
                            ad_external_id=draft.ad_external_id,
                            rule_code=rule.rule_code,
                            rule_name=rule.rule_name,
                            level=FindingLevel.L1,
                            severity=FindingSeverity(rule.severity),
                            entity_key=draft.entity_key,
                            issue_location=draft.issue_location,
                            impact_ru=draft.impact_ru,
                            recommendation_ru=draft.recommendation_ru,
                            evidence=draft.evidence,
                            fingerprint=fingerprint,
                            status=FindingStatus.new,
                            suspected_sabotage=False,
                            ai_verdict=None,
                        )
                    )

            can_close_previous = bool(context.campaigns)
            fixed_rows: list[Finding] = []
            if can_close_previous:
                fixed_rows = await self._history.apply_status_lifecycle(
                    account_id=account_id,
                    audit_id=audit.id,
                    level=FindingLevel.L1,
                    campaign_external_id=campaign_external_id,
                    current_findings=findings_rows,
                )
            await self._findings.bulk_create(findings_rows + fixed_rows)
            finished_at = datetime.now(timezone.utc)
            await self._audits.mark_completed(audit, finished_at)
            await self._logs.create(
                action="l1_audit_run",
                entity_type="audit",
                entity_key=str(audit.id),
                account_id=account_id,
                actor_user_id=actor_user_id,
                payload={
                    "catalog_version": active_catalog.version,
                    "l1_rules_total": len(l1_rules),
                    "findings_created": len(findings_rows),
                    "findings_fixed": len(fixed_rows),
                },
            )
            await self._session.commit()
        except Exception:
            finished_at = datetime.now(timezone.utc)
            await self._audits.mark_failed(audit, finished_at)
            await self._session.commit()
            raise

        return RunL1AuditResponse(
            audit_id=audit.id,
            account_id=account_id,
            catalog_version=active_catalog.version,
            status=audit.status.value,
            findings_created=len(findings_rows) + len(fixed_rows),
            started_at=audit.started_at,
            finished_at=audit.finished_at,
        )

    async def _build_context(self, account_id: UUID, *, campaign_external_id: str | None = None) -> L1Context:
        campaigns_all = self._latest_snapshots_as_dicts(
            await self._snapshots.list_by_account_and_type(account_id=account_id, entity_type=SnapshotEntityType.campaign)
        )
        groups_all = self._latest_snapshots_as_dicts(
            await self._snapshots.list_by_account_and_type(account_id=account_id, entity_type=SnapshotEntityType.ad_group)
        )
        ads_all = self._latest_snapshots_as_dicts(
            await self._snapshots.list_by_account_and_type(account_id=account_id, entity_type=SnapshotEntityType.ad)
        )
        keywords_all = self._latest_snapshots_as_dicts(
            await self._snapshots.list_by_account_and_type(account_id=account_id, entity_type=SnapshotEntityType.keyword)
        )
        extensions_all = self._latest_snapshots_as_dicts(
            await self._snapshots.list_by_account_and_type(account_id=account_id, entity_type=SnapshotEntityType.extension)
        )

        groups_all = [
            item
            for item in groups_all
            if str(item.get("status") or item.get("state") or "").lower() != "archived"
        ]
        active_group_ids_all = {str(item.get("id")) for item in groups_all if item.get("id") is not None}
        keywords_for_competition = [
            item
            for item in keywords_all
            if _is_active_state(item.get("state") or item.get("status"))
            and str(item.get("ad_group_id")) in active_group_ids_all
        ]
        campaigns_for_competition = [c for c in campaigns_all if _is_active_yandex_campaign(c)]

        campaigns = campaigns_all
        groups = groups_all
        ads = ads_all
        keywords = keywords_all
        extensions = extensions_all
        account_campaigns: list[dict] | None = None
        account_keywords: list[dict] | None = None
        scoped: str | None = None
        if campaign_external_id:
            scoped = campaign_external_id
            account_campaigns = campaigns_for_competition
            account_keywords = keywords_for_competition
            campaigns = [item for item in campaigns if str(item.get("id")) == campaign_external_id]
            groups = [item for item in groups if str(item.get("campaign_id")) == campaign_external_id]
            ads = [item for item in ads if str(item.get("campaign_id")) == campaign_external_id]
            keywords = [item for item in keywords if str(item.get("campaign_id")) == campaign_external_id]
            extensions = [item for item in extensions if str(item.get("campaign_id")) == campaign_external_id]

        active_group_ids = {str(item.get("id")) for item in groups if item.get("id") is not None}
        ads = [
            item
            for item in ads
            if _is_active_state(item.get("state") or item.get("status"))
            and str(item.get("ad_group_id")) in active_group_ids
        ]
        keywords = [
            item
            for item in keywords
            if _is_active_state(item.get("state") or item.get("status"))
            and str(item.get("ad_group_id")) in active_group_ids
        ]
        return L1Context(
            account_id=str(account_id),
            campaigns=campaigns,
            groups=groups,
            ads=ads,
            keywords=keywords,
            extensions=extensions,
            account_campaigns=account_campaigns,
            account_keywords=account_keywords,
            scoped_campaign_external_id=scoped,
        )

    @staticmethod
    def _latest_snapshots_as_dicts(snapshots: list[EntitySnapshot]) -> list[dict]:
        latest: dict[str, dict] = {}
        for row in snapshots:
            if row.entity_key in latest:
                continue
            latest[row.entity_key] = row.normalized_snapshot or {}
        return list(latest.values())

    @staticmethod
    def _fingerprint(rule_code: str, entity_key: str, evidence_signature: str) -> str:
        payload = f"{rule_code}|{entity_key}|{evidence_signature}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
