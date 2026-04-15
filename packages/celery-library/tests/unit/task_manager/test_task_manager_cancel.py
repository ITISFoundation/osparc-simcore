# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Tests that cancelling tasks calls revoke() so the worker skips them
without consuming rate-limit tokens, and that new tasks still complete
successfully after cancellation.
"""

from unittest.mock import patch

import pytest
from celery.worker.worker import WorkController  # pylint: disable=no-name-in-module
from celery_library._task_manager import CeleryTaskManager
from celery_library.errors import TaskOrGroupNotFoundError
from models_library.celery import (
    GroupExecutionMetadata,
    GroupTaskExecutionMetadata,
    OwnerMetadata,
    TaskExecutionMetadata,
    TaskState,
    TaskStatus,
)

from .conftest import (
    noop_task,
    wait_for_task_not_pending,
    wait_for_task_success,
)


async def test_cancel_single_task_calls_revoke(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    """Cancelling a single task must call revoke() on the AsyncResult
    so the worker skips it entirely.
    """
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner_metadata=fake_owner_metadata,
    )

    with patch("celery.result.AsyncResult.revoke") as mock_revoke:
        await task_manager.cancel(fake_owner_metadata, task_uuid)
        mock_revoke.assert_called_once()

    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_status(fake_owner_metadata, task_uuid)


async def test_cancel_group_calls_revoke_for_each_task(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    """Cancelling a group must call revoke() on every sub-task's
    AsyncResult.
    """
    num_tasks = 5
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=noop_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    group_uuid, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="rate_limited_group",
            tasks=group_tasks,
        ),
        owner_metadata=fake_owner_metadata,
    )

    with patch("celery.result.AsyncResult.revoke") as mock_revoke:
        await task_manager.cancel(fake_owner_metadata, group_uuid)
        assert mock_revoke.call_count == num_tasks

    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_status(fake_owner_metadata, group_uuid)

    for task_uuid in task_uuids:
        with pytest.raises(TaskOrGroupNotFoundError):
            await task_manager.get_status(fake_owner_metadata, task_uuid)


async def test_new_task_succeeds_after_cancelling_rate_limited_group(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    """After cancelling a group of rate-limited tasks, a newly submitted
    rate-limited task still completes successfully.
    """
    num_tasks = 5
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=noop_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    group_uuid, _ = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="rate_limited_group",
            tasks=group_tasks,
        ),
        owner_metadata=fake_owner_metadata,
    )

    await task_manager.cancel(fake_owner_metadata, group_uuid)

    new_task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner_metadata=fake_owner_metadata,
    )

    await wait_for_task_success(task_manager, fake_owner_metadata, new_task_uuid)

    status = await task_manager.get_status(fake_owner_metadata, new_task_uuid)
    assert isinstance(status, TaskStatus)
    assert status.task_state == TaskState.SUCCESS


async def test_new_task_succeeds_after_cancelling_single_rate_limited_task(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    """Cancel a single rate-limited task, then verify a new submission
    completes successfully.
    """
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner_metadata=fake_owner_metadata,
    )

    await wait_for_task_not_pending(task_manager, fake_owner_metadata, task_uuid)
    await task_manager.cancel(fake_owner_metadata, task_uuid)

    new_task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner_metadata=fake_owner_metadata,
    )

    await wait_for_task_success(task_manager, fake_owner_metadata, new_task_uuid)

    status = await task_manager.get_status(fake_owner_metadata, new_task_uuid)
    assert isinstance(status, TaskStatus)
    assert status.task_state == TaskState.SUCCESS
