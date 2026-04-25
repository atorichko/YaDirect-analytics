"""Unit tests for audit task registry (Redis + Celery revoke)."""

from unittest.mock import MagicMock, patch

from app.services import audit_task_registry as reg


@patch.object(reg, "_revoke")
@patch.object(reg, "_redis")
def test_revoke_for_new_batch_revokes_batch_and_campaign_keys(mock_redis: MagicMock, mock_revoke: MagicMock) -> None:
    r = mock_redis.return_value
    r.scan_iter.return_value = ["yda:audit_task:campaign:acc-1:c1", "yda:audit_task:campaign:acc-1:c2"]
    r.get.side_effect = ["t-c1", "t-c2", "t-batch"]  # two campaign keys then batch key

    reg.revoke_for_new_batch("acc-1")

    assert mock_revoke.call_count == 3
    r.delete.assert_called()


@patch.object(reg, "_revoke")
@patch.object(reg, "_redis")
def test_clear_batch_if_current_only_when_match(mock_redis: MagicMock, mock_revoke: MagicMock) -> None:
    r = mock_redis.return_value
    r.get.return_value = "task-a"
    reg.clear_batch_if_current("acc-1", "task-a")
    r.delete.assert_called_once()
    mock_revoke.assert_not_called()


@patch.object(reg, "_redis")
def test_clear_batch_if_current_skips_when_mismatch(mock_redis: MagicMock) -> None:
    r = mock_redis.return_value
    r.get.return_value = "other"
    reg.clear_batch_if_current("acc-1", "task-a")
    r.delete.assert_not_called()
