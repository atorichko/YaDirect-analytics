import asyncio
from datetime import datetime, timezone
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.models.app_setting import AppSetting
from app.repositories.ad_account import AdAccountRepository
from app.repositories.entity_snapshot import EntitySnapshotRepository
from app.services.ai_audit_service import AIAuditService
from app.services.l1_audit_service import L1AuditService
from app.services.l2_audit_service import L2AuditService
from app.services.l3_audit_service import L3AuditService
from app.workers.celery_app import celery_app


def _human_stage_label(stage: str) -> str:
    labels = {
        "L1": "Проверяем базовые настройки кампании",
        "L2": "Проверяем стратегию и бюджет",
        "L3": "Проверяем ссылки и разметку",
        "AI": "Формируем AI-рекомендации",
    }
    return labels.get(stage, "Выполняем проверку")


async def _touch_campaign_last_audit(account_id: str, campaign_id: str) -> None:
    key = f"campaign_last_audit:{account_id}:{campaign_id}"
    now = datetime.now(timezone.utc).isoformat()
    async with AsyncSessionLocal() as session:
        row = await session.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=now)
            session.add(row)
        else:
            row.value = now
        await session.commit()


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="app.workers.tasks.run_l1_audit")
def run_l1_audit_task(account_id: str, actor_user_id: str | None = None) -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            service = L1AuditService(session)
            result = await service.run_manual_l1_audit(
                account_id=UUID(account_id),
                actor_user_id=UUID(actor_user_id) if actor_user_id else None,
            )
            return result.model_dump(mode="json")

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.run_campaign_full_audit")
def run_campaign_full_audit_task(
    account_id: str,
    campaign_id: str,
    actor_user_id: str | None = None,
    max_entities: int = 20,
) -> dict:
    async def _run() -> dict:
        actor_uuid = UUID(actor_user_id) if actor_user_id else None
        async with AsyncSessionLocal() as session:
            l1 = await L1AuditService(session).run_manual_l1_audit(
                account_id=UUID(account_id),
                actor_user_id=actor_uuid,
                campaign_external_id=campaign_id,
            )
        async with AsyncSessionLocal() as session:
            l2 = await L2AuditService(session).run_manual_l2_audit(
                account_id=UUID(account_id),
                actor_user_id=actor_uuid,
                campaign_external_id=campaign_id,
            )
        async with AsyncSessionLocal() as session:
            l3 = await L3AuditService(session).run_manual_l3_audit(
                account_id=UUID(account_id),
                actor_user_id=actor_uuid,
                campaign_external_id=campaign_id,
            )
        async with AsyncSessionLocal() as session:
            ai = await AIAuditService(session).run_manual_ai_audit(
                account_id=UUID(account_id),
                actor_user_id=actor_uuid,
                max_entities=max_entities,
                campaign_external_id=campaign_id,
            )
        await _touch_campaign_last_audit(account_id=account_id, campaign_id=campaign_id)
        return {
            "account_id": account_id,
            "campaign_id": campaign_id,
            "l1_audit_id": str(l1.audit_id),
            "l2_audit_id": str(l2.audit_id),
            "l3_audit_id": str(l3.audit_id),
            "ai_audit_id": str(ai.audit_id),
        }

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.run_account_active_campaigns_full_audit", bind=True)
def run_account_active_campaigns_full_audit_task(
    self,
    account_id: str,
    actor_user_id: str | None = None,
    max_entities: int = 20,
) -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            repo = EntitySnapshotRepository(session)
            latest = await repo.list_latest_campaigns(account_id=UUID(account_id))
        active_campaign_ids = [
            str(item.get("id"))
            for item in latest
            if str(item.get("id") or "").strip()
            and str(item.get("status") or "").lower() in {"active", "on", "enabled"}
        ]

        total_steps = max(1, len(active_campaign_ids) * 4)
        done_steps = 0
        results: list[dict] = []
        actor_uuid = UUID(actor_user_id) if actor_user_id else None
        self.update_state(
            state="PROGRESS",
            meta={
                "progress_percent": 0,
                "current_step": (
                    f"Подготовка аудита: найдено активных кампаний {len(active_campaign_ids)}. "
                    "Собираем данные перед запуском."
                ),
            },
        )
        campaigns_total = len(active_campaign_ids)
        for campaign_index, campaign_id in enumerate(active_campaign_ids, start=1):
            for stage in ("L1", "L2", "L3", "AI"):
                stage_label = _human_stage_label(stage)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "progress_percent": int((done_steps / total_steps) * 100),
                        "current_step": f"Кампания {campaign_index}/{campaigns_total}: {stage_label}",
                    },
                )
                async with AsyncSessionLocal() as session:
                    if stage == "L1":
                        result = await L1AuditService(session).run_manual_l1_audit(
                            account_id=UUID(account_id),
                            actor_user_id=actor_uuid,
                            campaign_external_id=campaign_id,
                        )
                    elif stage == "L2":
                        result = await L2AuditService(session).run_manual_l2_audit(
                            account_id=UUID(account_id),
                            actor_user_id=actor_uuid,
                            campaign_external_id=campaign_id,
                        )
                    elif stage == "L3":
                        result = await L3AuditService(session).run_manual_l3_audit(
                            account_id=UUID(account_id),
                            actor_user_id=actor_uuid,
                            campaign_external_id=campaign_id,
                        )
                    else:
                        result = await AIAuditService(session).run_manual_ai_audit(
                            account_id=UUID(account_id),
                            actor_user_id=actor_uuid,
                            max_entities=max_entities,
                            campaign_external_id=campaign_id,
                        )
                done_steps += 1
                results.append(
                    {
                        "campaign_id": campaign_id,
                        "stage": stage,
                        "audit_id": str(result.audit_id),
                    }
                )
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "progress_percent": int((done_steps / total_steps) * 100),
                        "current_step": f"Кампания {campaign_index}/{campaigns_total}: этап завершен",
                    },
                )
            await _touch_campaign_last_audit(account_id=account_id, campaign_id=campaign_id)
        return {
            "account_id": account_id,
            "campaigns_total": len(active_campaign_ids),
            "steps_total": total_steps,
            "steps_done": done_steps,
            "details": results,
        }

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.run_l2_audit")
def run_l2_audit_task(account_id: str, actor_user_id: str | None = None) -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            service = L2AuditService(session)
            result = await service.run_manual_l2_audit(
                account_id=UUID(account_id),
                actor_user_id=UUID(actor_user_id) if actor_user_id else None,
            )
            return result.model_dump(mode="json")

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.run_l3_audit")
def run_l3_audit_task(account_id: str, actor_user_id: str | None = None) -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            service = L3AuditService(session)
            result = await service.run_manual_l3_audit(
                account_id=UUID(account_id),
                actor_user_id=UUID(actor_user_id) if actor_user_id else None,
            )
            return result.model_dump(mode="json")

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.run_ai_audit")
def run_ai_audit_task(account_id: str, actor_user_id: str | None = None, max_entities: int = 20) -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            service = AIAuditService(session)
            result = await service.run_manual_ai_audit(
                account_id=UUID(account_id),
                actor_user_id=UUID(actor_user_id) if actor_user_id else None,
                max_entities=max_entities,
            )
            return result.model_dump(mode="json")

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.weekly_sync_accounts")
def weekly_sync_accounts() -> dict:
    # Stage 11 scheduler: place-holder sync trigger for all active accounts.
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            repo = AdAccountRepository(session)
            account_ids = await repo.list_active_ids()
            return {
                "accounts_total": len(account_ids),
                "accounts": [str(item) for item in account_ids],
                "status": "sync_placeholder_completed",
            }

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.weekly_audit_accounts")
def weekly_audit_accounts() -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as session:
            repo = AdAccountRepository(session)
            account_ids = await repo.list_active_ids()
        launched = 0
        for account_id in account_ids:
            run_l1_audit_task.delay(str(account_id))
            run_l2_audit_task.delay(str(account_id))
            run_l3_audit_task.delay(str(account_id))
            run_ai_audit_task.delay(str(account_id))
            launched += 4
        return {
            "accounts_total": len(account_ids),
            "jobs_launched": launched,
        }

    return asyncio.run(_run())
