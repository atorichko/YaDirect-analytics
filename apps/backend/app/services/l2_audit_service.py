from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit import AuditTrigger
from app.models.entity_snapshot import EntitySnapshot, SnapshotEntityType
from app.models.finding import Finding, FindingLevel, FindingSeverity, FindingStatus
from app.repositories.action_log import ActionLogRepository
from app.repositories.ad_account import AdAccountRepository
from app.repositories.audit import AuditRepository
from app.repositories.entity_snapshot import EntitySnapshotRepository
from app.repositories.finding import FindingRepository
from app.repositories.rule_catalog import RuleCatalogRepository
from app.schemas.audit import RunL2AuditResponse
from app.services.finding_history_service import FindingHistoryService
from app.services.l2_rules import L2Context, build_l2_rule_registry


class L2AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._accounts = AdAccountRepository(session)
        self._audits = AuditRepository(session)
        self._snapshots = EntitySnapshotRepository(session)
        self._findings = FindingRepository(session)
        self._history = FindingHistoryService(self._findings)
        self._logs = ActionLogRepository(session)
        self._catalog_repo = RuleCatalogRepository(session)
        self._registry = build_l2_rule_registry()

    async def run_manual_l2_audit(
        self,
        *,
        account_id: UUID,
        actor_user_id: UUID | None,
        campaign_external_id: str | None = None,
    ) -> RunL2AuditResponse:
        account = await self._accounts.get_by_id(account_id)
        if account is None:
            raise LookupError("Ad account not found")

        active_catalog = await self._catalog_repo.get_active("yandex_direct")
        if active_catalog is None:
            raise LookupError("Active rule catalog not found")
        rules = await self._catalog_repo.list_rules(str(active_catalog.id))
        l2_rules = [r for r in rules if r.enabled and r.level == "L2" and r.check_type == "deterministic"]

        audit = await self._audits.create(
            account_id=account_id,
            trigger=AuditTrigger.manual,
            catalog_version=active_catalog.version,
            initiated_by_user_id=actor_user_id,
        )
        await self._audits.mark_running(audit, datetime.now(timezone.utc))
        await self._session.flush()

        try:
            context = await self._build_context(account_id, campaign_external_id=campaign_external_id)
            findings_rows: list[Finding] = []
            for rule in l2_rules:
                handler = self._registry.get(rule.rule_code)
                if handler is None:
                    continue
                raw_rule = dict(rule.config or {})
                raw_rule.setdefault("recommendation_ru", rule.rule_name)
                raw_rule.setdefault("min_conversions_for_learning", settings.min_conversions_for_learning)
                raw_rule.setdefault("budget_limited_days_threshold", settings.chronic_budget_limited_days_threshold)
                drafts = handler(context, raw_rule)
                for draft in drafts:
                    evidence_signature = self._evidence_signature(draft.evidence)
                    fingerprint = self._fingerprint(rule.rule_code, draft.entity_key, evidence_signature)
                    findings_rows.append(
                        Finding(
                            audit_id=audit.id,
                            account_id=account_id,
                            campaign_external_id=draft.campaign_external_id,
                            group_external_id=draft.group_external_id,
                            ad_external_id=draft.ad_external_id,
                            rule_code=rule.rule_code,
                            rule_name=rule.rule_name,
                            level=FindingLevel.L2,
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

            fixed_rows = await self._history.apply_status_lifecycle(
                account_id=account_id,
                audit_id=audit.id,
                level=FindingLevel.L2,
                campaign_external_id=campaign_external_id,
                current_findings=findings_rows,
            )
            await self._findings.bulk_create(findings_rows + fixed_rows)
            await self._audits.mark_completed(audit, datetime.now(timezone.utc))
            await self._logs.create(
                action="l2_audit_run",
                entity_type="audit",
                entity_key=str(audit.id),
                account_id=account_id,
                actor_user_id=actor_user_id,
                payload={
                    "catalog_version": active_catalog.version,
                    "l2_rules_total": len(l2_rules),
                    "findings_created": len(findings_rows),
                    "findings_fixed": len(fixed_rows),
                },
            )
            await self._session.commit()
        except Exception:
            await self._audits.mark_failed(audit, datetime.now(timezone.utc))
            await self._session.commit()
            raise

        return RunL2AuditResponse(
            audit_id=audit.id,
            account_id=account_id,
            catalog_version=active_catalog.version,
            status=audit.status.value,
            findings_created=len(findings_rows) + len(fixed_rows),
            started_at=audit.started_at,
            finished_at=audit.finished_at,
        )

    async def _build_context(self, account_id: UUID, *, campaign_external_id: str | None = None) -> L2Context:
        campaigns = self._latest_snapshots_as_dicts(
            await self._snapshots.list_by_account_and_type(account_id=account_id, entity_type=SnapshotEntityType.campaign)
        )
        if campaign_external_id:
            campaigns = [item for item in campaigns if str(item.get("id")) == campaign_external_id]
        metrika_goals: list[dict] = []
        account_rows = await self._snapshots.list_by_account_and_type(
            account_id=account_id, entity_type=SnapshotEntityType.account
        )
        for row in account_rows:
            if row.entity_key != "metrika":
                continue
            norm = row.normalized_snapshot or {}
            goals = norm.get("goals")
            if isinstance(goals, list):
                metrika_goals = [g for g in goals if isinstance(g, dict)]
            break
        return L2Context(account_id=str(account_id), campaigns=campaigns, metrika_goals=metrika_goals)

    @staticmethod
    def _latest_snapshots_as_dicts(snapshots: list[EntitySnapshot]) -> list[dict]:
        latest: dict[str, dict] = {}
        for row in snapshots:
            if row.entity_key in latest:
                continue
            latest[row.entity_key] = row.normalized_snapshot or {}
        return list(latest.values())

    @staticmethod
    def _evidence_signature(evidence: dict) -> str:
        return json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _fingerprint(rule_code: str, entity_key: str, evidence_signature: str) -> str:
        payload = f"{rule_code}|{entity_key}|{evidence_signature}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
