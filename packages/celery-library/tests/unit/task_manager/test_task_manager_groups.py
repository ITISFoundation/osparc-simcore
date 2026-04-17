# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import contextlib

import pytest
from celery.worker.worker import WorkController  # pylint: disable=no-name-in-module
from celery_library._task_manager import CeleryTaskManager
from celery_library.errors import TaskOrGroupNotFoundError, TransferableCeleryError
from faker import Faker
from models_library.celery import (
    GroupExecutionMetadata,
    GroupStatus,
    GroupTaskExecutionMetadata,
    GroupUUID,
    TaskExecutionMetadata,
    TaskUUID,
)
from pydantic import TypeAdapter
from tenacity import AsyncRetrying

from .conftest import (
    _TENACITY_RETRY_PARAMS,
    dreamer_task,
    failure_task,
    fake_file_processor,
    streaming_results_task,
    wait_for_task_done,
    wait_for_task_success,
)

_faker = Faker()


async def test_submit_group_all_tasks_complete_successfully(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group of tasks
    num_tasks = 3
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": [f"file{i}-{j}" for j in range(2)]},
        )
        for i in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        execution_metadata=GroupExecutionMetadata(
            name="fake_file_processing_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    assert group_id is not None
    assert len(task_uuids) == num_tasks

    # Wait for all tasks to complete
    for task_uuid in task_uuids:
        await wait_for_task_success(task_manager, task_uuid)

    # Verify all results
    for task_uuid in task_uuids:
        result = await task_manager.get_result(task_uuid)
        assert result == "archive.zip"


async def test_submit_group_tasks_appear_in_listing(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group of tasks
    num_tasks = 4
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=dreamer_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    task_uuids: list[TaskUUID] = []

    try:
        _, task_uuids = await task_manager.submit_group(
            GroupExecutionMetadata(
                name="tasks_group",
                tasks=group_tasks,
            ),
            owner=fake_owner,
            user_id=fake_user_id,
        )

        # Verify none of group tasks appear in listing
        async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
            with attempt:
                tasks = await task_manager.list_tasks(owner=fake_owner, user_id=fake_user_id)
                task_uuids_from_list = {task.uuid for task in tasks}
                assert all(uuid not in task_uuids_from_list for uuid in task_uuids)
    finally:
        # Clean up
        for task_uuid in task_uuids:
            with contextlib.suppress(TaskOrGroupNotFoundError):
                await task_manager.cancel(task_uuid)


async def test_submit_group_with_mixed_task_types(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group with different task types
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file1", "file2"]},
        ),
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file3"]},
        ),
        (
            GroupTaskExecutionMetadata(name=streaming_results_task.__name__, ephemeral=False),
            {"num_results": 2},
        ),
    ]

    _, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="mixed_tasks_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    assert len(task_uuids) == 3

    # Wait for all tasks to complete
    for task_uuid in task_uuids:
        await wait_for_task_success(task_manager, task_uuid)

    # Verify first two tasks return "archive.zip"
    assert await task_manager.get_result(task_uuids[0]) == "archive.zip"
    assert await task_manager.get_result(task_uuids[1]) == "archive.zip"

    # Verify streaming task result
    result = await task_manager.get_result(task_uuids[2])
    assert result == "completed-2-results"


async def test_submit_group_can_cancel_individual_tasks(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group of long-running tasks
    num_tasks = 3
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=dreamer_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    _, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="cancellable_tasks_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    # Wait a bit to ensure tasks are running
    await asyncio.sleep(2.0)

    # Cancel the first task
    await task_manager.cancel(task_uuids[0])

    # Verify first task is gone
    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_status(task_uuids[0])

    # Cancel remaining tasks
    for task_uuid in task_uuids[1:]:
        await task_manager.cancel(task_uuid)


async def test_cancelling_a_group_cancels_all_tasks(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    num_tasks = 3
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=dreamer_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    group_uuid, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="cancellable_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    # Wait a bit to ensure tasks are running
    await asyncio.sleep(2.0)

    await task_manager.cancel(group_uuid)

    # Group itself should no longer exist
    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_status(group_uuid)

    # All individual tasks should also be gone
    for task_uuid in task_uuids:
        with pytest.raises(TaskOrGroupNotFoundError):
            await task_manager.get_status(task_uuid)


async def test_submit_group_with_failures(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group with some failing tasks
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file1"]},
        ),
        (
            GroupTaskExecutionMetadata(name=failure_task.__name__),
            {},
        ),
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file2"]},
        ),
    ]

    _, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="group_with_failures",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    assert len(task_uuids) == 3

    # Wait for all tasks to finish
    for task_uuid in task_uuids:
        await wait_for_task_done(task_manager, task_uuid)

    # Verify successful tasks
    assert await task_manager.get_result(task_uuids[0]) == "archive.zip"
    assert await task_manager.get_result(task_uuids[2]) == "archive.zip"

    # Verify failed task
    result = await task_manager.get_result(task_uuids[1])
    assert isinstance(result, TransferableCeleryError)
    assert "Something strange happened: BOOM!" in f"{result}"


async def test_submit_group_with_ephemeral_tasks(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group with ephemeral tasks
    num_tasks = 2
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__, ephemeral=True),
            {"files": [f"file{i}"]},
        )
        for i in range(num_tasks)
    ]

    _, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="ephemeral_tasks_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    assert len(task_uuids) == num_tasks

    # Wait for all tasks to complete and get results (which should clean them up)
    for task_uuid in task_uuids:
        await wait_for_task_success(task_manager, task_uuid)

        # Getting the result should trigger cleanup for ephemeral tasks
        result = await task_manager.get_result(task_uuid)
        assert result == "archive.zip"

    for task_uuid in task_uuids:
        # Second attempt to get result should fail as ephemeral tasks are cleaned up
        with pytest.raises(TaskOrGroupNotFoundError):
            await task_manager.get_status(task_uuid)


async def test_submit_empty_group(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    _, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="empty_group",
            tasks=[],
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    assert task_uuids == []


async def test_get_group_status_returns_status_for_running_group(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group of long-running tasks
    num_tasks = 3
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=dreamer_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="running_tasks_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    try:
        # Wait a moment to ensure tasks start
        await asyncio.sleep(1.0)

        # Get group status while tasks are running
        group_status = await task_manager.get_status(group_id)

        assert isinstance(group_status, GroupStatus)
        assert group_status.group_uuid == group_id
        assert group_status.task_uuids == task_uuids
        assert group_status.total_count == num_tasks
        assert group_status.completed_count >= 0
        assert group_status.completed_count <= num_tasks
    finally:
        # Clean up
        for task_uuid in task_uuids:
            with contextlib.suppress(TaskOrGroupNotFoundError):
                await task_manager.cancel(task_uuid)


async def test_get_group_status_returns_done_when_all_tasks_complete(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group of fast tasks
    num_tasks = 2
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": [f"file{i}"]},
        )
        for i in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="fast_tasks_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    # Wait for all tasks to complete
    for task_uuid in task_uuids:
        await wait_for_task_success(task_manager, task_uuid)

    # Get group status
    group_status = await task_manager.get_status(group_id)

    assert isinstance(group_status, GroupStatus)
    assert group_status.group_uuid == group_id
    assert group_status.task_uuids == task_uuids
    assert group_status.total_count == num_tasks
    assert group_status.completed_count == num_tasks
    assert group_status.is_done
    assert group_status.is_successful


async def test_get_group_status_successful_false_when_task_fails(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group with one failing task
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file1"]},
        ),
        (
            GroupTaskExecutionMetadata(name=failure_task.__name__),
            {},
        ),
    ]

    group_id, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="failing_tasks_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    # Wait for all tasks to finish
    for task_uuid in task_uuids:
        await wait_for_task_done(task_manager, task_uuid)

    # Get group status
    group_status = await task_manager.get_status(group_id)

    assert isinstance(group_status, GroupStatus)
    assert group_status.group_uuid == group_id
    assert group_status.task_uuids == task_uuids
    assert group_status.total_count == 2
    assert group_status.is_done
    # NOTE: one task failed
    assert group_status.completed_count == 1
    assert not group_status.is_successful


async def test_get_group_status_with_nonexistent_group_raises_error(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    fake_group_uuid = TypeAdapter(GroupUUID).validate_python(_faker.uuid4())

    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_status(fake_group_uuid)


async def test_get_group_status_tracks_progress(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit a group of longer-running tasks
    num_tasks = 4
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": [f"file{i}-{j}" for j in range(3)]},
        )
        for i in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="long_running_tasks_group",
            tasks=group_tasks,
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    try:
        # Check status repeatedly until group completes, tracking progress
        previous_completed = 0
        group_status = None
        async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
            with attempt:
                group_status = await task_manager.get_status(group_id)

                assert isinstance(group_status, GroupStatus)
                # Progress should never go backwards
                assert group_status.completed_count >= previous_completed
                previous_completed = group_status.completed_count

                # Keep retrying until done
                assert group_status.is_done

        # Verify final status
        assert group_status is not None
        assert group_status.total_count == num_tasks
        assert group_status.is_successful
    finally:
        # Clean up
        for task_uuid in task_uuids:
            with contextlib.suppress(TaskOrGroupNotFoundError):
                await task_manager.cancel(task_uuid)


async def test_get_group_status_with_empty_group(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    # Submit an empty group
    group_id, _ = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="empty_group",
            tasks=[],
        ),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    # Get group status
    group_status = await task_manager.get_status(group_id)

    assert isinstance(group_status, GroupStatus)
    assert group_status.group_uuid == group_id
    assert group_status.task_uuids == []
    assert group_status.total_count == 0
    assert group_status.completed_count == 0
    assert group_status.is_done
    assert group_status.is_successful


async def test_get_result_dispatches_to_task_result(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    task_uuid = await task_manager.submit_task(
        TaskExecutionMetadata(name=fake_file_processor.__name__),
        owner=fake_owner,
        user_id=fake_user_id,
        files=["file1"],
    )
    await wait_for_task_success(task_manager, task_uuid)

    result = await task_manager.get_result(task_uuid)
    assert result == "archive.zip"


async def test_get_result_dispatches_to_group_result(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": [f"file{i}"]},
        )
        for i in range(2)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(name="result_dispatch_group", tasks=group_tasks),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    for task_uuid in task_uuids:
        await wait_for_task_success(task_manager, task_uuid)

    result = await task_manager.get_result(group_id)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(r == "archive.zip" for r in result)


async def test_get_result_with_nonexistent_uuid_raises_error(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    fake_uuid = TypeAdapter(TaskUUID).validate_python(_faker.uuid4())
    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_result(fake_uuid)


async def test_get_group_result_returns_all_results(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    num_tasks = 3
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": [f"file{i}"]},
        )
        for i in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(name="all_results_group", tasks=group_tasks),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    for task_uuid in task_uuids:
        await wait_for_task_success(task_manager, task_uuid)

    results = await task_manager.get_result(group_id)
    assert results == ["archive.zip"] * num_tasks


async def test_get_group_result_with_failures(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file1"]},
        ),
        (
            GroupTaskExecutionMetadata(name=failure_task.__name__),
            {},
        ),
    ]

    group_id, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(name="failures_result_group", tasks=group_tasks),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    for task_uuid in task_uuids:
        await wait_for_task_done(task_manager, task_uuid)

    results = await task_manager.get_result(group_id)
    assert len(results) == 2
    assert results[0] == "archive.zip"
    assert isinstance(results[1], TransferableCeleryError)
    assert "Something strange happened: BOOM!" in f"{results[1]}"


async def test_get_group_result_with_ephemeral_cleans_up(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    num_tasks = 2
    group_tasks = [
        (
            GroupTaskExecutionMetadata(name=fake_file_processor.__name__, ephemeral=True),
            {"files": [f"file{i}"]},
        )
        for i in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(name="ephemeral_result_group", tasks=group_tasks, ephemeral=True),
        owner=fake_owner,
        user_id=fake_user_id,
    )

    for task_uuid in task_uuids:
        await wait_for_task_success(task_manager, task_uuid)

    # First call returns results and triggers cleanup
    results = await task_manager.get_result(group_id)
    assert results == ["archive.zip"] * num_tasks

    # Second call should fail because the group was cleaned up
    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_result(group_id)


async def test_get_group_result_with_nonexistent_group_raises_error(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner: str,
    fake_user_id: int,
):
    fake_group_uuid = TypeAdapter(GroupUUID).validate_python(_faker.uuid4())
    with pytest.raises(TaskOrGroupNotFoundError):
        await task_manager.get_result(fake_group_uuid)
