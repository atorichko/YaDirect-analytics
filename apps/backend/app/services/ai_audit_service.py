from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.polza_ai.client import PolzaAIClient
from app.models.app_setting import AppSetting
from app.models.audit import AuditTrigger
from app.models.entity_snapshot import EntitySnapshot, SnapshotEntityType
from app.models.finding import Finding, FindingLevel, FindingSeverity, FindingStatus
from app.repositories.ad_account import AdAccountRepository
from app.repositories.ai_interaction import AIInteractionRepository
from app.repositories.audit import AuditRepository
from app.repositories.entity_snapshot import EntitySnapshotRepository
from app.repositories.finding import FindingRepository
from app.repositories.rule_catalog import RuleCatalogRepository
from app.schemas.audit import RunAIAuditResponse
from app.core.ai_prompt_defaults import DEFAULT_AI_ANALYSIS_PROMPT_PREFIX
from app.services.finding_history_service import FindingHistoryService


def _is_active_state(value: object) -> bool:
    return str(value or "").lower() in {"active", "on", "enabled"}


class AIAuditService:
    PROMPT_SETTING_KEY = "ai_analysis_prompt"
    DEFAULT_PROMPT_PREFIX = DEFAULT_AI_ANALYSIS_PROMPT_PREFIX

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._accounts = AdAccountRepository(session)
        self._audits = AuditRepository(session)
        self._snapshots = EntitySnapshotRepository(session)
        self._findings = FindingRepository(session)
        self._history = FindingHistoryService(self._findings)
        self._catalog_repo = RuleCatalogRepository(session)
        self._ai_logs = AIInteractionRepository(session)
        self._ai_client = PolzaAIClient()

    async def run_manual_ai_audit(
        self,
        *,
        account_id: UUID,
        actor_user_id: UUID | None,
        max_entities: int = 20,
        campaign_external_id: str | None = None,
    ) -> RunAIAuditResponse:
        account = await self._accounts.get_by_id(account_id)
        if account is None:
            raise LookupError("Ad account not found")
        active_catalog = await self._catalog_repo.get_active("yandex_direct")
        if active_catalog is None:
            raise LookupError("Active rule catalog not found")
        rules = await self._catalog_repo.list_rules(str(active_catalog.id))
        ai_rules = [r for r in rules if r.enabled and r.check_type == "ai_assisted"]

        audit = await self._audits.create(
            account_id=account_id,
            trigger=AuditTrigger.manual,
            catalog_version=active_catalog.version,
            initiated_by_user_id=actor_user_id,
        )
        await self._audits.mark_running(audit, datetime.now(timezone.utc))
        await self._session.flush()

        ai_calls_total = 0
        ai_calls_failed = 0
        findings_rows: list[Finding] = []
        try:
            entities = await self._load_candidate_entities(
                account_id=account_id,
                max_entities=max_entities,
                campaign_external_id=campaign_external_id,
            )
            prompt_prefix = await self._get_prompt_prefix()
            for rule in ai_rules:
                for entity in entities:
                    ai_calls_total += 1
                    prompt = self._build_prompt(
                        prompt_prefix=prompt_prefix,
                        rule_code=rule.rule_code,
                        rule_name=rule.rule_name,
                        entity=entity,
                    )
                    try:
                        result = await asyncio.to_thread(self._ai_client.evaluate, prompt=prompt)
                        verdict = result.verdict
                        await self._ai_logs.create(
                            audit_id=audit.id,
                            account_id=account_id,
                            rule_code=rule.rule_code,
                            entity_key=verdict.entity_key,
                            provider="polza.ai",
                            model=result.model,
                            status="ok",
                            prompt=result.prompt,
                            response_raw=result.raw_response,
                            response_json=verdict.model_dump(),
                            latency_ms=result.latency_ms,
                        )
                        if verdict.result in {"fail", "needs_review"}:
                            evidence_signature = self._evidence_signature(verdict.evidence)
                            fingerprint = self._fingerprint(verdict.rule_code, verdict.entity_key, evidence_signature)
                            findings_rows.append(
                                Finding(
                                    audit_id=audit.id,
                                    account_id=account_id,
                                    campaign_external_id=entity.get("campaign_external_id"),
                                    group_external_id=entity.get("group_external_id"),
                                    ad_external_id=entity.get("ad_external_id"),
                                    rule_code=verdict.rule_code,
                                    rule_name=rule.rule_name,
                                    level=FindingLevel(rule.level),
                                    severity=FindingSeverity(verdict.severity),
                                    entity_key=verdict.entity_key,
                                    issue_location=verdict.entity_key,
                                    impact_ru=verdict.impact_ru,
                                    recommendation_ru=verdict.recommendation_ru,
                                    evidence=verdict.evidence,
                                    fingerprint=fingerprint,
                                    status=FindingStatus.new,
                                    suspected_sabotage=False,
                                    ai_verdict=verdict.model_dump(),
                                )
                            )
                    except Exception as exc:  # noqa: BLE001
                        ai_calls_failed += 1
                        await self._ai_logs.create(
                            audit_id=audit.id,
                            account_id=account_id,
                            rule_code=rule.rule_code,
                            entity_key=str(entity.get("entity_key")),
                            provider="polza.ai",
                            model="unknown",
                            status="error",
                            prompt=prompt,
                            response_raw=None,
                            response_json=None,
                            error_message=str(exc),
                        )

            fixed_rows = await self._history.apply_status_lifecycle(
                account_id=account_id,
                audit_id=audit.id,
                level=None,
                campaign_external_id=campaign_external_id,
                current_findings=findings_rows,
                require_ai_verdict_for_previous=True,
            )
            await self._findings.bulk_create(findings_rows + fixed_rows)
            await self._audits.mark_completed(audit, datetime.now(timezone.utc))
            await self._session.commit()
        except Exception:
            await self._audits.mark_failed(audit, datetime.now(timezone.utc))
            await self._session.commit()
            raise

        return RunAIAuditResponse(
            audit_id=audit.id,
            account_id=account_id,
            catalog_version=active_catalog.version,
            status=audit.status.value,
            findings_created=len(findings_rows) + len(fixed_rows),
            ai_calls_total=ai_calls_total,
            ai_calls_failed=ai_calls_failed,
            started_at=audit.started_at,
            finished_at=audit.finished_at,
        )

    async def _load_candidate_entities(
        self,
        *,
        account_id: UUID,
        max_entities: int,
        campaign_external_id: str | None = None,
    ) -> list[dict]:
        ad_snapshots = await self._snapshots.list_by_account_and_type(account_id=account_id, entity_type=SnapshotEntityType.ad)
        latest = [item for item in self._latest_snapshots_as_dicts(ad_snapshots) if _is_active_state(item.get("state") or item.get("status"))][
            :max_entities
        ]
        if campaign_external_id:
            latest = [item for item in latest if str(item.get("campaign_id")) == campaign_external_id][:max_entities]
        entities: list[dict] = []
        for ad in latest:
            ad_id = str(ad.get("id"))
            entities.append(
                {
                    "entity_key": f"ad:{ad_id}",
                    "campaign_external_id": str(ad.get("campaign_id")) if ad.get("campaign_id") is not None else None,
                    "group_external_id": str(ad.get("ad_group_id")) if ad.get("ad_group_id") is not None else None,
                    "ad_external_id": ad_id,
                    "payload": ad,
                }
            )
        return entities

    async def _get_prompt_prefix(self) -> str:
        row = await self._session.get(AppSetting, self.PROMPT_SETTING_KEY)
        if row is None or not row.value.strip():
            return self.DEFAULT_PROMPT_PREFIX
        return row.value.strip()

    @staticmethod
    def _build_prompt(*, prompt_prefix: str, rule_code: str, rule_name: str, entity: dict) -> str:
        schema = {
            "rule_code": "string",
            "entity_key": "string",
            "result": "pass|fail|needs_review",
            "severity": "warning|high|critical",
            "confidence": 0.0,
            "evidence": {},
            "impact_ru": "string",
            "recommendation_ru": "string",
            "reasoning_short_ru": "string",
        }
        return (
            f"{prompt_prefix}\n"
            "Проведи AI-assisted аудит сущности Яндекс Директ.\n"
            f"Правило: {rule_code} ({rule_name})\n"
            f"Сущность: {json.dumps(entity, ensure_ascii=False)}\n"
            f"Ответ строго JSON по схеме: {json.dumps(schema, ensure_ascii=False)}\n"
            f"rule_code='{rule_code}', entity_key='{entity.get('entity_key')}'."
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
    def _evidence_signature(evidence: dict) -> str:
        return json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _fingerprint(rule_code: str, entity_key: str, evidence_signature: str) -> str:
        payload = f"{rule_code}|{entity_key}|{evidence_signature}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
