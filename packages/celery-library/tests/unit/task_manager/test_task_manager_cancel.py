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
from celery_library.errors import TaskNotFoundError
from models_library.celery import (
    GroupExecutionMetadata,
    GroupTaskExecutionMetadata,
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
    fake_owner: str,
    fake_user_id: int,
):
    """Cancelling a single task must call revoke() on the AsyncResult
    so the worker skips it entirely.
    """
    task_id = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    with (
        patch("celery.result.AsyncResult.ready", return_value=False),
        patch("celery.result.AsyncResult.revoke") as mock_revoke,
    ):
        await task_manager.cancel(task_id)
        mock_revoke.assert_called_once()

    with pytest.raises(TaskNotFoundError):
        await task_manager.get_status(task_id)


async def test_cancel_single_task_skips_revoke_when_already_finished(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    """An already-finished task must not be revoked: revoke() broadcasts to
    all workers and grows their in-memory revoked-tasks set, which is
    wasteful (and noisy) when the task is already done.
    """
    task_id = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    with (
        patch("celery.result.AsyncResult.ready", return_value=True),
        patch("celery.result.AsyncResult.revoke") as mock_revoke,
    ):
        await task_manager.cancel(task_id)
        mock_revoke.assert_not_called()

    with pytest.raises(TaskNotFoundError):
        await task_manager.get_status(task_id)


async def test_cancel_group_calls_revoke_for_each_task(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
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

    group_id, task_ids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="rate_limited_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    with (
        patch("celery.result.AsyncResult.ready", return_value=False),
        patch("celery.result.AsyncResult.revoke") as mock_revoke,
    ):
        await task_manager.cancel(group_id)
        assert mock_revoke.call_count == num_tasks

    with pytest.raises(TaskNotFoundError):
        await task_manager.get_status(group_id)

    for task_id in task_ids:
        with pytest.raises(TaskNotFoundError):
            await task_manager.get_status(task_id)


async def test_new_task_succeeds_after_cancelling_rate_limited_group(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
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
        owner=fake_owner,
        user_id=fake_user_id,
    )

    await task_manager.cancel(group_uuid)

    new_task_id = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    await wait_for_task_success(task_manager, new_task_id)

    status = await task_manager.get_status(new_task_id)
    assert isinstance(status, TaskStatus)
    assert status.task_state == TaskState.SUCCESS


async def test_new_task_succeeds_after_cancelling_single_rate_limited_task(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    """Cancel a single rate-limited task, then verify a new submission
    completes successfully.
    """
    task_id = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    await wait_for_task_not_pending(task_manager, task_id)
    await task_manager.cancel(task_id)

    new_task_id = await task_manager.submit_task(
        TaskExecutionMetadata(name=noop_task.__name__),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    await wait_for_task_success(task_manager, new_task_id)

    status = await task_manager.get_status(new_task_id)
    assert isinstance(status, TaskStatus)
    assert status.task_state == TaskState.SUCCESS
