"""Track running Celery audit tasks per account/campaign; revoke superseded jobs."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_BATCH_KEY = "yda:audit_task:batch:{account_id}"
_CAMP_PREFIX = "yda:audit_task:campaign:{account_id}:"
_LOCK_PREFIX = "yda:audit_lock:"
_TTL_SEC = 6 * 3600


def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _revoke(task_id: str, *, terminate: bool = True) -> None:
    if not task_id:
        return
    try:
        from app.workers.celery_app import celery_app

        celery_app.control.revoke(task_id, terminate=terminate, signal="SIGTERM")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to revoke Celery task %s: %s", task_id, exc)


def _scan_campaign_keys(r: redis.Redis, account_id: str) -> list[str]:
    pattern = f"{_CAMP_PREFIX.format(account_id=account_id)}*"
    return list(r.scan_iter(match=pattern))


@contextmanager
def exclusive_audit_mutations(account_id: str, *, wait_seconds: float = 25.0) -> None:
    """Serialize enqueue/revoke for one ad account (avoids duplicate Celery tasks)."""
    r = _redis()
    key = f"{_LOCK_PREFIX}{account_id}"
    deadline = time.monotonic() + wait_seconds
    acquired = False
    while time.monotonic() < deadline:
        if r.set(key, "1", nx=True, ex=60):
            acquired = True
            break
        time.sleep(0.05)
    if not acquired:
        raise TimeoutError(f"audit_lock_timeout:{account_id}")
    try:
        yield
    finally:
        r.delete(key)


def revoke_for_new_batch(account_id: str) -> None:
    """Revoke running batch and all per-campaign audit tasks tracked for this account."""
    r = _redis()
    aid = str(account_id)
    for ck in _scan_campaign_keys(r, aid):
        old = r.get(ck)
        if old:
            _revoke(old)
        r.delete(ck)
    bkey = _BATCH_KEY.format(account_id=aid)
    old_batch = r.get(bkey)
    if old_batch:
        _revoke(old_batch)
    r.delete(bkey)


def revoke_for_new_campaign_audit(account_id: str, campaign_id: str) -> None:
    """Revoke running batch (conflicts with single-campaign run) and prior run for same campaign."""
    r = _redis()
    aid = str(account_id)
    cid = str(campaign_id)
    bkey = _BATCH_KEY.format(account_id=aid)
    old_batch = r.get(bkey)
    if old_batch:
        _revoke(old_batch)
    r.delete(bkey)
    ckey = f"{_CAMP_PREFIX.format(account_id=aid)}{cid}"
    old_c = r.get(ckey)
    if old_c:
        _revoke(old_c)
    r.delete(ckey)


def register_batch(account_id: str, task_id: str) -> None:
    _redis().set(_BATCH_KEY.format(account_id=str(account_id)), str(task_id), ex=_TTL_SEC)


def register_campaign(account_id: str, campaign_id: str, task_id: str) -> None:
    aid = str(account_id)
    ckey = f"{_CAMP_PREFIX.format(account_id=aid)}{str(campaign_id)}"
    _redis().set(ckey, str(task_id), ex=_TTL_SEC)


def clear_batch_if_current(account_id: str, task_id: str) -> None:
    r = _redis()
    bkey = _BATCH_KEY.format(account_id=str(account_id))
    if r.get(bkey) == str(task_id):
        r.delete(bkey)


def clear_campaign_if_current(account_id: str, campaign_id: str, task_id: str) -> None:
    r = _redis()
    ckey = f"{_CAMP_PREFIX.format(account_id=str(account_id))}{str(campaign_id)}"
    if r.get(ckey) == str(task_id):
        r.delete(ckey)


def get_registered_batch_task_id(account_id: str) -> str | None:
    v = _redis().get(_BATCH_KEY.format(account_id=str(account_id)))
    return str(v) if v else None
