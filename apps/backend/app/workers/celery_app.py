from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "yadirect_analytics",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "weekly-account-sync": {
            "task": "app.workers.tasks.weekly_sync_accounts",
            "schedule": crontab(
                minute=settings.weekly_cron_minute,
                hour=settings.weekly_cron_hour,
                day_of_week=settings.weekly_cron_day_of_week,
            ),
        },
        "weekly-account-audit": {
            "task": "app.workers.tasks.weekly_audit_accounts",
            "schedule": crontab(
                minute=settings.weekly_cron_minute,
                hour=str((int(settings.weekly_cron_hour) + 1) % 24) if settings.weekly_cron_hour.isdigit() else "4",
                day_of_week=settings.weekly_cron_day_of_week,
            ),
        },
    },
)
