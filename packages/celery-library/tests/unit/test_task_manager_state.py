import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from celery import states
from celery_library import CeleryTaskManager
from models_library.celery import OwnerMetadata, TaskExecutionMetadata, TaskState, TaskStatus


@pytest.mark.parametrize(
    "celery_state,expected",
    [
        (states.FAILURE, TaskState.FAILURE),
        (states.IGNORED, TaskState.FAILURE),
        (states.PENDING, TaskState.PENDING),
        (states.RECEIVED, TaskState.PENDING),
        (states.REJECTED, TaskState.PENDING),
        (states.RETRY, TaskState.RETRY),
        (states.REVOKED, TaskState.FAILURE),
        (states.STARTED, TaskState.STARTED),
        (states.SUCCESS, TaskState.SUCCESS),
    ],
)
async def test_get_status_maps_celery_state_to_task_state(
    task_manager_mock: CeleryTaskManager,
    celery_app_mock: MagicMock,
    task_store_mock: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
    celery_state: str,
    expected: TaskState,
):
    task_store_mock.task_or_group_exists.return_value = True
    task_store_mock.get_task_metadata.return_value = TaskExecutionMetadata(name="a_task")
    celery_app_mock.AsyncResult.return_value.state = celery_state

    status = await task_manager_mock.get_status(fake_owner_metadata, uuid4())

    assert isinstance(status, TaskStatus)
    assert status.task_state == expected


async def test_get_status_of_revoked_task_is_terminal(
    task_manager_mock: CeleryTaskManager,
    celery_app_mock: MagicMock,
    task_store_mock: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
):
    """Celery >= 5.6 persists REVOKED in the result backend on cancellation:
    polling must resolve to a terminal state instead of crashing with ValueError.
    """
    task_store_mock.task_or_group_exists.return_value = True
    task_store_mock.get_task_metadata.return_value = TaskExecutionMetadata(name="a_task")
    celery_app_mock.AsyncResult.return_value.state = states.REVOKED

    status = await task_manager_mock.get_status(fake_owner_metadata, uuid4())

    assert isinstance(status, TaskStatus)
    assert status.task_state == TaskState.FAILURE
    assert status.is_done


async def test_get_status_of_unknown_celery_state_maps_to_pending_and_logs(
    task_manager_mock: CeleryTaskManager,
    celery_app_mock: MagicMock,
    task_store_mock: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
    caplog: pytest.LogCaptureFixture,
):
    task_store_mock.task_or_group_exists.return_value = True
    task_store_mock.get_task_metadata.return_value = TaskExecutionMetadata(name="a_task")
    celery_app_mock.AsyncResult.return_value.state = "SOME_FUTURE_CELERY_STATE"

    with caplog.at_level(logging.WARNING):
        status = await task_manager_mock.get_status(fake_owner_metadata, uuid4())

    assert isinstance(status, TaskStatus)
    assert status.task_state == TaskState.PENDING
    assert "SOME_FUTURE_CELERY_STATE" in caplog.text
