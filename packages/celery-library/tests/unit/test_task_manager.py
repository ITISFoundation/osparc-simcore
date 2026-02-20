# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from random import randint

import pytest
from celery import Celery, Task  # pylint: disable=no-name-in-module
from celery.worker.worker import WorkController  # pylint: disable=no-name-in-module
from celery_library._task_manager import CeleryTaskManager
from celery_library.errors import GroupNotFoundError, TaskNotFoundError, TransferableCeleryError
from celery_library.task import register_task
from celery_library.worker.app_server import get_app_server
from common_library.errors_classes import OsparcErrorMixin
from faker import Faker
from models_library.progress_bar import ProgressReport
from pydantic import TypeAdapter
from servicelib.celery.models import (
    TASK_DONE_STATES,
    ExecutionMetadata,
    GroupUUID,
    OwnerMetadata,
    TaskKey,
    TaskState,
    TaskStreamItem,
    TaskUUID,
    Wildcard,
)
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

_faker = Faker()

_logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = ["redis"]
pytest_simcore_ops_services_selection = []

_TENACITY_RETRY_PARAMS = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "stop": stop_after_delay(30),
    "wait": wait_fixed(0.1),
}


async def _fake_file_processor(celery_app: Celery, task_name: str, task_key: str, files: list[str]) -> str:
    def sleep_for(seconds: float) -> None:
        time.sleep(seconds)

    for n, file in enumerate(files, start=1):
        with log_context(_logger, logging.INFO, msg=f"Processing file {file}"):
            await get_app_server(celery_app).task_manager.set_task_progress(
                task_key=task_key,
                report=ProgressReport(actual_value=n / len(files)),
            )
            await asyncio.get_event_loop().run_in_executor(None, sleep_for, 1)

    return "archive.zip"


def fake_file_processor(task: Task, task_key: TaskKey, files: list[str]) -> str:
    assert task_key
    assert task.name
    _logger.info("Calling _fake_file_processor")
    return asyncio.run_coroutine_threadsafe(
        _fake_file_processor(task.app, task.name, task.request.id, files),
        get_app_server(task.app).event_loop,
    ).result()


class MyError(OsparcErrorMixin, Exception):
    msg_template = "Something strange happened: {msg}"


def failure_task(task: Task, task_key: TaskKey) -> None:
    assert task_key
    assert task
    msg = "BOOM!"
    raise MyError(msg=msg)


async def dreamer_task(task: Task, task_key: TaskKey) -> list[int]:
    numbers = []
    for _ in range(30):
        numbers.append(randint(1, 90))  # noqa: S311
        await asyncio.sleep(0.5)
    return numbers


def streaming_results_task(task: Task, task_key: TaskKey, num_results: int = 5) -> str:
    assert task_key
    assert task.name

    async def _stream_results(sleep_interval: float) -> None:
        app_server = get_app_server(task.app)
        for i in range(num_results):
            result_data = f"result-{i}"
            result_item = TaskStreamItem(data=result_data)
            await app_server.task_manager.push_task_stream_items(
                task_key,
                result_item,
            )
            _logger.info("Pushed result %d: %s", i, result_data)
            await asyncio.sleep(sleep_interval)

        # Mark the stream as done
        await app_server.task_manager.set_task_stream_done(task_key)

    # Run the streaming in the event loop
    asyncio.run_coroutine_threadsafe(_stream_results(0.5), get_app_server(task.app).event_loop).result()

    return f"completed-{num_results}-results"


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        register_task(celery_app, fake_file_processor)
        register_task(celery_app, failure_task)
        register_task(celery_app, dreamer_task)
        register_task(celery_app, streaming_results_task)

    return _


async def _wait_for_task_success(
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
) -> None:
    """Wait for a task to reach SUCCESS state."""
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS


async def _wait_for_task_done(
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
) -> None:
    """Wait for a task to reach any DONE state."""
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state in TASK_DONE_STATES


async def test_submitting_task_calling_async_function_results_with_success_state(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner_metadata=fake_owner_metadata,
        files=[f"file{n}" for n in range(5)],
    )

    await _wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

    assert (await task_manager.get_task_status(fake_owner_metadata, task_uuid)).task_state == TaskState.SUCCESS
    assert (await task_manager.get_task_result(fake_owner_metadata, task_uuid)) == "archive.zip"


async def test_submitting_task_with_failure_results_with_error(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=failure_task.__name__,
        ),
        owner_metadata=fake_owner_metadata,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            raw_result = await task_manager.get_task_result(fake_owner_metadata, task_uuid)
            assert isinstance(raw_result, TransferableCeleryError)

    raw_result = await task_manager.get_task_result(fake_owner_metadata, task_uuid)
    assert f"{raw_result}" == "Something strange happened: BOOM!"


async def test_cancelling_a_running_task_aborts_and_deletes(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner_metadata=fake_owner_metadata,
    )

    await asyncio.sleep(3.0)

    await task_manager.cancel_task(fake_owner_metadata, task_uuid)

    with pytest.raises(TaskNotFoundError):
        await task_manager.get_task_status(fake_owner_metadata, task_uuid)

    assert task_uuid not in await task_manager.list_tasks(fake_owner_metadata)


async def test_listing_task_uuids_contains_submitted_task(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner_metadata=fake_owner_metadata,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            tasks = await task_manager.list_tasks(fake_owner_metadata)
            assert any(task.uuid == task_uuid for task in tasks)

    tasks = await task_manager.list_tasks(fake_owner_metadata)
    assert any(task.uuid == task_uuid for task in tasks)


async def test_filtering_listing_tasks(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
):
    class MyOwnerMetadata(OwnerMetadata):
        user_id: int
        product_name: str | Wildcard

    user_id = 42
    owner = "test-owner"
    expected_task_uuids: set[TaskUUID] = set()
    all_tasks: list[tuple[TaskUUID, MyOwnerMetadata]] = []

    try:
        for _ in range(5):
            owner_metadata = MyOwnerMetadata(user_id=user_id, product_name=_faker.word(), owner=owner)
            task_uuid = await task_manager.submit_task(
                ExecutionMetadata(
                    name=dreamer_task.__name__,
                ),
                owner_metadata=owner_metadata,
            )
            expected_task_uuids.add(task_uuid)
            all_tasks.append((task_uuid, owner_metadata))

        for _ in range(3):
            owner_metadata = MyOwnerMetadata(
                user_id=_faker.pyint(min_value=100, max_value=200),
                product_name=_faker.word(),
                owner=owner,
            )
            task_uuid = await task_manager.submit_task(
                ExecutionMetadata(
                    name=dreamer_task.__name__,
                ),
                owner_metadata=owner_metadata,
            )
            all_tasks.append((task_uuid, owner_metadata))

        search_owner_metadata = MyOwnerMetadata(
            user_id=user_id,
            product_name="*",
            owner=owner,
        )
        tasks = await task_manager.list_tasks(search_owner_metadata)
        assert expected_task_uuids == {task.uuid for task in tasks}
    finally:
        # clean up all tasks. this should ideally be done in the fixture
        for task_uuid, owner_metadata in all_tasks:
            await task_manager.cancel_task(owner_metadata, task_uuid)


async def test_push_task_result_streams_data_during_execution(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    num_results = 3

    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=streaming_results_task.__name__,
            ephemeral=False,  # Keep task available after completion for result pulling
        ),
        owner_metadata=fake_owner_metadata,
        num_results=num_results,
    )

    # Pull results while task is running, retry until is_done is True
    results = []
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            result, is_done, _ = await task_manager.pull_task_stream_items(fake_owner_metadata, task_uuid, limit=10)
            results.extend(result)
            assert is_done

    # Should have at least some results streamed
    assert results == [TaskStreamItem(data=f"result-{i}") for i in range(num_results)]

    # Wait for task completion
    await _wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

    # Final task result should be available
    final_result = await task_manager.get_task_result(fake_owner_metadata, task_uuid)
    assert final_result == f"completed-{num_results}-results"

    # After task completion, try to pull any remaining results
    remaining_results, is_done, _ = await task_manager.pull_task_stream_items(fake_owner_metadata, task_uuid, limit=10)
    assert remaining_results == []
    assert is_done


async def test_pull_task_stream_items_with_limit(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit task with fewer results to make it more predictable
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=streaming_results_task.__name__,
            ephemeral=False,  # Keep task available after completion for result pulling
        ),
        owner_metadata=fake_owner_metadata,
        num_results=5,
    )

    # Wait for task to complete
    await _wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

    # Pull all results in one go to avoid consumption issues
    all_results, is_done_final, _last_update_final = await task_manager.pull_task_stream_items(
        fake_owner_metadata,
        task_uuid,
        limit=20,  # High limit to get all items
    )

    assert all_results is not None

    assert len(all_results) == 5  # Can't have more than what was created
    assert is_done_final

    # Verify result format for any results we got
    for result in all_results:
        assert result.data.startswith("result-")


async def test_pull_task_stream_items_from_nonexistent_task_raises_error(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    fake_task_uuid = TypeAdapter(TaskUUID).validate_python(_faker.uuid4())

    with pytest.raises(TaskNotFoundError):
        await task_manager.pull_task_stream_items(fake_owner_metadata, fake_task_uuid)


async def test_push_task_stream_items_to_nonexistent_task_raises_error(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
):
    not_existing_task_id = "not_existing"

    with pytest.raises(TaskNotFoundError):
        await task_manager.push_task_stream_items(not_existing_task_id, TaskStreamItem(data="some-result"))


async def test_submit_group_all_tasks_complete_successfully(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group of tasks
    num_tasks = 3
    executions = [
        (
            ExecutionMetadata(name=fake_file_processor.__name__),
            {"files": [f"file{i}-{j}" for j in range(2)]},
        )
        for i in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    assert group_id is not None
    assert len(task_uuids) == num_tasks

    # Wait for all tasks to complete
    for task_uuid in task_uuids:
        await _wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

    # Verify all results
    for task_uuid in task_uuids:
        result = await task_manager.get_task_result(fake_owner_metadata, task_uuid)
        assert result == "archive.zip"


async def test_submit_group_tasks_appear_in_listing(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group of tasks
    num_tasks = 4
    executions = [
        (
            ExecutionMetadata(name=dreamer_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    try:
        _, task_uuids = await task_manager.submit_group(
            executions,
            owner_metadata=fake_owner_metadata,
        )

        # Verify all tasks appear in listing
        async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
            with attempt:
                tasks = await task_manager.list_tasks(fake_owner_metadata)
                task_uuids_from_list = {task.uuid for task in tasks}
                assert all(uuid in task_uuids_from_list for uuid in task_uuids)
    finally:
        # Clean up
        for task_uuid in task_uuids:
            with contextlib.suppress(TaskNotFoundError):
                await task_manager.cancel_task(fake_owner_metadata, task_uuid)


async def test_submit_group_with_mixed_task_types(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group with different task types
    executions = [
        (
            ExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file1", "file2"]},
        ),
        (
            ExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file3"]},
        ),
        (
            ExecutionMetadata(name=streaming_results_task.__name__, ephemeral=False),
            {"num_results": 2},
        ),
    ]

    _, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    assert len(task_uuids) == 3

    # Wait for all tasks to complete
    for task_uuid in task_uuids:
        await _wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

    # Verify first two tasks return "archive.zip"
    assert await task_manager.get_task_result(fake_owner_metadata, task_uuids[0]) == "archive.zip"
    assert await task_manager.get_task_result(fake_owner_metadata, task_uuids[1]) == "archive.zip"

    # Verify streaming task result
    result = await task_manager.get_task_result(fake_owner_metadata, task_uuids[2])
    assert result == "completed-2-results"


async def test_submit_group_can_cancel_individual_tasks(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group of long-running tasks
    num_tasks = 3
    executions = [
        (
            ExecutionMetadata(name=dreamer_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    _, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    # Wait a bit to ensure tasks are running
    await asyncio.sleep(2.0)

    # Cancel the first task
    await task_manager.cancel_task(fake_owner_metadata, task_uuids[0])

    # Verify first task is gone
    with pytest.raises(TaskNotFoundError):
        await task_manager.get_task_status(fake_owner_metadata, task_uuids[0])

    # Cancel remaining tasks
    for task_uuid in task_uuids[1:]:
        await task_manager.cancel_task(fake_owner_metadata, task_uuid)


async def test_submit_group_with_failures(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group with some failing tasks
    executions = [
        (
            ExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file1"]},
        ),
        (
            ExecutionMetadata(name=failure_task.__name__),
            {},
        ),
        (
            ExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file2"]},
        ),
    ]

    _, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    assert len(task_uuids) == 3

    # Wait for all tasks to finish
    for task_uuid in task_uuids:
        await _wait_for_task_done(task_manager, fake_owner_metadata, task_uuid)

    # Verify successful tasks
    assert await task_manager.get_task_result(fake_owner_metadata, task_uuids[0]) == "archive.zip"
    assert await task_manager.get_task_result(fake_owner_metadata, task_uuids[2]) == "archive.zip"

    # Verify failed task
    result = await task_manager.get_task_result(fake_owner_metadata, task_uuids[1])
    assert isinstance(result, TransferableCeleryError)
    assert "Something strange happened: BOOM!" in f"{result}"


async def test_submit_group_with_ephemeral_tasks(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group with ephemeral tasks
    num_tasks = 2
    executions = [
        (
            ExecutionMetadata(name=fake_file_processor.__name__, ephemeral=True),
            {"files": [f"file{i}"]},
        )
        for i in range(num_tasks)
    ]

    _, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    assert len(task_uuids) == num_tasks

    # Wait for all tasks to complete and get results (which should clean them up)
    for task_uuid in task_uuids:
        await _wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

        # Getting the result should trigger cleanup for ephemeral tasks
        result = await task_manager.get_task_result(fake_owner_metadata, task_uuid)
        assert result == "archive.zip"

    for task_uuid in task_uuids:
        # Second attempt to get result should fail as ephemeral tasks are cleaned up
        with pytest.raises(TaskNotFoundError):
            await task_manager.get_task_status(fake_owner_metadata, task_uuid)


async def test_submit_empty_group(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    _, task_uuids = await task_manager.submit_group(
        [],
        owner_metadata=fake_owner_metadata,
    )

    assert task_uuids == []


async def test_get_group_status_returns_status_for_running_group(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group of long-running tasks
    num_tasks = 3
    executions = [
        (
            ExecutionMetadata(name=dreamer_task.__name__),
            {},
        )
        for _ in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    try:
        # Wait a moment to ensure tasks start
        await asyncio.sleep(1.0)

        # Get group status while tasks are running
        group_status = await task_manager.get_group_status(fake_owner_metadata, group_id)

        assert group_status.group_uuid == group_id
        assert group_status.task_uuids == task_uuids
        assert group_status.total_count == num_tasks
        assert group_status.completed_count >= 0
        assert group_status.completed_count <= num_tasks
    finally:
        # Clean up
        for task_uuid in task_uuids:
            with contextlib.suppress(TaskNotFoundError):
                await task_manager.cancel_task(fake_owner_metadata, task_uuid)


async def test_get_group_status_returns_done_when_all_tasks_complete(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group of fast tasks
    num_tasks = 2
    executions = [
        (
            ExecutionMetadata(name=fake_file_processor.__name__),
            {"files": [f"file{i}"]},
        )
        for i in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    # Wait for all tasks to complete
    for task_uuid in task_uuids:
        await _wait_for_task_success(task_manager, fake_owner_metadata, task_uuid)

    # Get group status
    group_status = await task_manager.get_group_status(fake_owner_metadata, group_id)

    assert group_status.group_uuid == group_id
    assert group_status.task_uuids == task_uuids
    assert group_status.total_count == num_tasks
    assert group_status.completed_count == num_tasks
    assert group_status.is_done
    assert group_status.is_successful


async def test_get_group_status_successful_false_when_task_fails(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group with one failing task
    executions = [
        (
            ExecutionMetadata(name=fake_file_processor.__name__),
            {"files": ["file1"]},
        ),
        (
            ExecutionMetadata(name=failure_task.__name__),
            {},
        ),
    ]

    group_id, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    # Wait for all tasks to finish
    for task_uuid in task_uuids:
        await _wait_for_task_done(task_manager, fake_owner_metadata, task_uuid)

    # Get group status
    group_status = await task_manager.get_group_status(fake_owner_metadata, group_id)

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
    fake_owner_metadata: OwnerMetadata,
):
    fake_group_uuid = TypeAdapter(GroupUUID).validate_python(_faker.uuid4())

    with pytest.raises(GroupNotFoundError):
        await task_manager.get_group_status(fake_owner_metadata, fake_group_uuid)


async def test_get_group_status_tracks_progress(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit a group of longer-running tasks
    num_tasks = 4
    executions = [
        (
            ExecutionMetadata(name=fake_file_processor.__name__),
            {"files": [f"file{i}-{j}" for j in range(3)]},
        )
        for i in range(num_tasks)
    ]

    group_id, task_uuids = await task_manager.submit_group(
        executions,
        owner_metadata=fake_owner_metadata,
    )

    try:
        # Check status repeatedly until group completes, tracking progress
        previous_completed = 0
        async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
            with attempt:
                group_status = await task_manager.get_group_status(fake_owner_metadata, group_id)

                # Progress should never go backwards
                assert group_status.completed_count >= previous_completed
                previous_completed = group_status.completed_count

                # Keep retrying until done
                assert group_status.is_done

        # Verify final status
        assert group_status.total_count == num_tasks
        assert group_status.is_successful
    finally:
        # Clean up
        for task_uuid in task_uuids:
            with contextlib.suppress(TaskNotFoundError):
                await task_manager.cancel_task(fake_owner_metadata, task_uuid)


async def test_get_group_status_with_empty_group(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
    fake_owner_metadata: OwnerMetadata,
):
    # Submit an empty group
    group_id, _ = await task_manager.submit_group(
        [],
        owner_metadata=fake_owner_metadata,
    )

    # Get group status
    group_status = await task_manager.get_group_status(fake_owner_metadata, group_id)

    assert group_status.group_uuid == group_id
    assert group_status.task_uuids == []
    assert group_status.total_count == 0
    assert group_status.completed_count == 0
    assert group_status.is_done
    assert group_status.is_successful
