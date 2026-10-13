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
    mocked_task_manager: CeleryTaskManager,
    mocked_celery_app: MagicMock,
    mocked_task_store: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
    celery_state: str,
    expected: TaskState,
):
    mocked_task_store.task_or_group_exists.return_value = True
    mocked_task_store.get_task_metadata.return_value = TaskExecutionMetadata(name="a_task")
    mocked_celery_app.AsyncResult.return_value.state = celery_state

    status = await mocked_task_manager.get_status(fake_owner_metadata, uuid4())

    assert isinstance(status, TaskStatus)
    assert status.task_state == expected


async def test_get_status_of_revoked_task_is_terminal(
    mocked_task_manager: CeleryTaskManager,
    mocked_celery_app: MagicMock,
    mocked_task_store: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
):
    """Celery >= 5.6 persists REVOKED in the result backend on cancellation:
    polling must resolve to a terminal state instead of crashing with ValueError.
    """
    mocked_task_store.task_or_group_exists.return_value = True
    mocked_task_store.get_task_metadata.return_value = TaskExecutionMetadata(name="a_task")
    mocked_celery_app.AsyncResult.return_value.state = states.REVOKED

    status = await mocked_task_manager.get_status(fake_owner_metadata, uuid4())

    assert isinstance(status, TaskStatus)
    assert status.task_state == TaskState.FAILURE
    assert status.is_done


async def test_get_status_of_unknown_celery_state_maps_to_pending_and_logs(
    mocked_task_manager: CeleryTaskManager,
    mocked_celery_app: MagicMock,
    mocked_task_store: AsyncMock,
    fake_owner_metadata: OwnerMetadata,
    caplog: pytest.LogCaptureFixture,
):
    mocked_task_store.task_or_group_exists.return_value = True
    mocked_task_store.get_task_metadata.return_value = TaskExecutionMetadata(name="a_task")
    mocked_celery_app.AsyncResult.return_value.state = "SOME_FUTURE_CELERY_STATE"

    with caplog.at_level(logging.WARNING):
        status = await mocked_task_manager.get_status(fake_owner_metadata, uuid4())

    assert isinstance(status, TaskStatus)
    assert status.task_state == TaskState.PENDING
    assert "SOME_FUTURE_CELERY_STATE" in caplog.text
