import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.schemas.audit import (
    AccountAutostartSettings,
    JobStatusResponse,
    QueueCampaignAuditJobRequest,
    QueueCampaignBatchAuditJobRequest,
    QueueAuditJobRequest,
    QueueAuditJobResponse,
    QueueWeeklyJobResponse,
    RunAIAuditRequest,
    RunAIAuditResponse,
    RunL1AuditRequest,
    RunL1AuditResponse,
    RunL2AuditRequest,
    RunL2AuditResponse,
    RunL3AuditRequest,
    RunL3AuditResponse,
)
from app.models.app_setting import AppSetting
from app.models.entity_snapshot import SnapshotEntityType
from app.services.ai_audit_service import AIAuditService
from app.services.l1_audit_service import L1AuditService
from app.services.l2_audit_service import L2AuditService
from app.services.l3_audit_service import L3AuditService
from app.workers.celery_app import celery_app
from app.workers.tasks import (
    run_ai_audit_task,
    run_account_active_campaigns_full_audit_task,
    run_campaign_full_audit_task,
    run_l1_audit_task,
    run_l2_audit_task,
    run_l3_audit_task,
    weekly_audit_accounts,
    weekly_sync_accounts,
)

router = APIRouter(prefix="/audits", tags=["audits"])


@router.post("/l1/run", response_model=RunL1AuditResponse, status_code=status.HTTP_201_CREATED)
async def run_l1_audit(
    body: RunL1AuditRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunL1AuditResponse:
    service = L1AuditService(session)
    try:
        return await service.run_manual_l1_audit(account_id=body.account_id, actor_user_id=user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/l1/run-job", response_model=QueueAuditJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_l1_audit_job(body: QueueAuditJobRequest, user: CurrentUser) -> QueueAuditJobResponse:
    task = run_l1_audit_task.delay(str(body.account_id), str(user.id))
    return QueueAuditJobResponse(task_id=task.id, task_name="run_l1_audit", status="queued")


@router.post("/ai/run", response_model=RunAIAuditResponse, status_code=status.HTTP_201_CREATED)
async def run_ai_audit(
    body: RunAIAuditRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunAIAuditResponse:
    service = AIAuditService(session)
    try:
        return await service.run_manual_ai_audit(
            account_id=body.account_id,
            actor_user_id=user.id,
            max_entities=body.max_entities,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/ai/run-job", response_model=QueueAuditJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_ai_audit_job(body: QueueAuditJobRequest, user: CurrentUser) -> QueueAuditJobResponse:
    task = run_ai_audit_task.delay(str(body.account_id), str(user.id), body.max_entities)
    return QueueAuditJobResponse(task_id=task.id, task_name="run_ai_audit", status="queued")


@router.post("/l2/run", response_model=RunL2AuditResponse, status_code=status.HTTP_201_CREATED)
async def run_l2_audit(
    body: RunL2AuditRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunL2AuditResponse:
    service = L2AuditService(session)
    try:
        return await service.run_manual_l2_audit(account_id=body.account_id, actor_user_id=user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/l2/run-job", response_model=QueueAuditJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_l2_audit_job(body: QueueAuditJobRequest, user: CurrentUser) -> QueueAuditJobResponse:
    task = run_l2_audit_task.delay(str(body.account_id), str(user.id))
    return QueueAuditJobResponse(task_id=task.id, task_name="run_l2_audit", status="queued")


@router.post("/l3/run", response_model=RunL3AuditResponse, status_code=status.HTTP_201_CREATED)
async def run_l3_audit(
    body: RunL3AuditRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunL3AuditResponse:
    service = L3AuditService(session)
    try:
        return await service.run_manual_l3_audit(account_id=body.account_id, actor_user_id=user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/l3/run-job", response_model=QueueAuditJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_l3_audit_job(body: QueueAuditJobRequest, user: CurrentUser) -> QueueAuditJobResponse:
    task = run_l3_audit_task.delay(str(body.account_id), str(user.id))
    return QueueAuditJobResponse(task_id=task.id, task_name="run_l3_audit", status="queued")


@router.post("/weekly/sync/run-job", response_model=QueueWeeklyJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_weekly_sync_job(_user: CurrentUser) -> QueueWeeklyJobResponse:
    task = weekly_sync_accounts.delay()
    return QueueWeeklyJobResponse(task_id=task.id, task_name="weekly_sync_accounts", status="queued")


@router.post("/weekly/audit/run-job", response_model=QueueWeeklyJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_weekly_audit_job(_user: CurrentUser) -> QueueWeeklyJobResponse:
    task = weekly_audit_accounts.delay()
    return QueueWeeklyJobResponse(task_id=task.id, task_name="weekly_audit_accounts", status="queued")


@router.get("/jobs/{task_id}", response_model=JobStatusResponse)
async def get_job_status(task_id: str, _user: CurrentUser) -> JobStatusResponse:
    result = celery_app.AsyncResult(task_id)
    payload: dict | str | None = None
    progress_percent: int | None = None
    current_step: str | None = None
    info = result.info
    if isinstance(info, dict):
        progress_percent = info.get("progress_percent")
        current_step = info.get("current_step")
    if result.ready():
        payload = result.result if isinstance(result.result, (dict, str)) else str(result.result)
        if result.successful() and progress_percent is None:
            progress_percent = 100
            current_step = "Аудит завершен"
        elif not result.successful() and current_step is None:
            current_step = "Ошибка выполнения аудита"
    return JobStatusResponse(
        task_id=task_id,
        state=result.state,
        ready=result.ready(),
        successful=(result.successful() if result.ready() else None),
        result=payload,
        progress_percent=progress_percent,
        current_step=current_step,
    )


@router.post("/campaign/run-job", response_model=QueueAuditJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_campaign_audit_job(body: QueueCampaignAuditJobRequest, user: CurrentUser) -> QueueAuditJobResponse:
    task = run_campaign_full_audit_task.delay(str(body.account_id), body.campaign_id, str(user.id), body.max_entities)
    return QueueAuditJobResponse(task_id=task.id, task_name="run_campaign_full_audit", status="queued")


@router.post("/campaigns/run-active-job", response_model=QueueAuditJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_active_campaigns_audit_job(
    body: QueueCampaignBatchAuditJobRequest,
    user: CurrentUser,
) -> QueueAuditJobResponse:
    task = run_account_active_campaigns_full_audit_task.delay(str(body.account_id), str(user.id), body.max_entities)
    return QueueAuditJobResponse(task_id=task.id, task_name="run_account_active_campaigns_full_audit", status="queued")


@router.get("/autostart/{account_id}", response_model=AccountAutostartSettings)
async def get_autostart_settings(
    account_id: str,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AccountAutostartSettings:
    key = f"autostart:{account_id}"
    row = await session.get(AppSetting, key)
    if row is None:
        return AccountAutostartSettings(enabled=False, every_n_days=7, start_date=datetime.now(timezone.utc).date().isoformat())
    payload = json.loads(row.value)
    return AccountAutostartSettings(
        enabled=bool(payload.get("enabled", False)),
        every_n_days=int(payload.get("every_n_days", 7)),
        start_date=str(payload.get("start_date")),
    )


@router.put("/autostart/{account_id}", response_model=AccountAutostartSettings)
async def set_autostart_settings(
    account_id: str,
    body: AccountAutostartSettings,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AccountAutostartSettings:
    key = f"autostart:{account_id}"
    payload = {
        "enabled": body.enabled,
        "every_n_days": max(1, int(body.every_n_days)),
        "start_date": body.start_date,
    }
    row = await session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=json.dumps(payload, ensure_ascii=False))
        session.add(row)
    else:
        row.value = json.dumps(payload, ensure_ascii=False)
    await session.commit()
    return AccountAutostartSettings(**payload)


@router.get("/campaign-last-run/{account_id}")
async def get_campaign_last_run_map(
    account_id: str,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    prefix = f"campaign_last_audit:{account_id}:"
    result = await session.execute(select(AppSetting).where(AppSetting.key.like(f"{prefix}%")))
    rows = list(result.scalars().all())
    out: dict[str, str] = {}
    for row in rows:
        campaign_id = row.key.removeprefix(prefix)
        if campaign_id:
            out[campaign_id] = row.value
    return out
