# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
import time
from collections.abc import Callable
from random import randint

import pytest
from celery import Celery, Task  # pylint: disable=no-name-in-module
from celery.worker.worker import WorkController  # pylint: disable=no-name-in-module
from celery_library.errors import TaskNotFoundError, TransferableCeleryError
from celery_library.task import register_task
from celery_library.worker.app_server import get_app_server
from common_library.errors_classes import OsparcErrorMixin
from faker import Faker
from models_library.progress_bar import ProgressReport
from servicelib.celery.models import (
    ExecutionMetadata,
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


class MyOwnerMetadata(OwnerMetadata):
    user_id: int


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


async def test_submitting_task_calling_async_function_results_with_success_state(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner_metadata=owner_metadata,
        files=[f"file{n}" for n in range(5)],
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    assert (await task_manager.get_task_status(owner_metadata, task_uuid)).task_state == TaskState.SUCCESS
    assert (await task_manager.get_task_result(owner_metadata, task_uuid)) == "archive.zip"


async def test_submitting_task_with_failure_results_with_error(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=failure_task.__name__,
        ),
        owner_metadata=owner_metadata,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            raw_result = await task_manager.get_task_result(owner_metadata, task_uuid)
            assert isinstance(raw_result, TransferableCeleryError)

    raw_result = await task_manager.get_task_result(owner_metadata, task_uuid)
    assert f"{raw_result}" == "Something strange happened: BOOM!"


async def test_cancelling_a_running_task_aborts_and_deletes(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner_metadata=owner_metadata,
    )

    await asyncio.sleep(3.0)

    await task_manager.cancel_task(owner_metadata, task_uuid)

    with pytest.raises(TaskNotFoundError):
        await task_manager.get_task_status(owner_metadata, task_uuid)

    tasks = await task_manager.list_tasks(owner_metadata)
    assert task_uuid not in [task.uuid for task in tasks]
    assert task_uuid not in await task_manager.list_tasks(owner_metadata)


async def test_listing_task_uuids_contains_submitted_task(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner_metadata=owner_metadata,
    )

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            tasks = await task_manager.list_tasks(owner_metadata)
            assert any(task.uuid == task_uuid for task in tasks)

    tasks = await task_manager.list_tasks(owner_metadata)
    assert any(task.uuid == task_uuid for task in tasks)


async def test_filtering_listing_tasks(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
):
    class MyOwnerMetadata(OwnerMetadata):
        user_id: int
        product_name: str | Wildcard

    user_id = 42
    _owner = "test-owner"
    expected_task_uuids: set[TaskUUID] = set()
    all_tasks: list[tuple[TaskUUID, MyOwnerMetadata]] = []

    try:
        for _ in range(5):
            owner_metadata = MyOwnerMetadata(user_id=user_id, product_name=_faker.word(), owner=_owner)
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
                owner=_owner,
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
            owner=_owner,
        )
        tasks = await task_manager.list_tasks(search_owner_metadata)
        assert expected_task_uuids == {task.uuid for task in tasks}
    finally:
        # clean up all tasks. this should ideally be done in the fixture
        for task_uuid, owner_metadata in all_tasks:
            await task_manager.cancel_task(owner_metadata, task_uuid)


async def test_push_task_result_streams_data_during_execution(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    num_results = 3

    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=streaming_results_task.__name__,
            ephemeral=False,  # Keep task available after completion for result pulling
        ),
        owner_metadata=owner_metadata,
        num_results=num_results,
    )

    # Pull results while task is running, retry until is_done is True
    results = []
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            result, is_done, _ = await task_manager.pull_task_stream_items(owner_metadata, task_uuid, limit=10)
            results.extend(result)
            assert is_done

    # Should have at least some results streamed
    assert results == [TaskStreamItem(data=f"result-{i}") for i in range(num_results)]

    # Wait for task completion
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    # Final task result should be available
    final_result = await task_manager.get_task_result(owner_metadata, task_uuid)
    assert final_result == f"completed-{num_results}-results"

    # After task completion, try to pull any remaining results
    remaining_results, is_done, _ = await task_manager.pull_task_stream_items(owner_metadata, task_uuid, limit=10)
    assert remaining_results == []
    assert is_done


async def test_pull_task_stream_items_with_limit(
    task_manager: TaskManager,
    with_celery_worker: WorkController,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    # Submit task with fewer results to make it more predictable
    task_uuid = await task_manager.submit_task(
        ExecutionMetadata(
            name=streaming_results_task.__name__,
            ephemeral=False,  # Keep task available after completion for result pulling
        ),
        owner_metadata=owner_metadata,
        num_results=5,
    )

    # Wait for task to complete
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    # Pull all results in one go to avoid consumption issues
    all_results, is_done_final, _last_update_final = await task_manager.pull_task_stream_items(
        owner_metadata,
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
    task_manager: TaskManager,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")
    fake_task_uuid = TaskUUID(_faker.uuid4())

    with pytest.raises(TaskNotFoundError):
        await task_manager.pull_task_stream_items(owner_metadata, fake_task_uuid)


async def test_push_task_stream_items_to_nonexistent_task_raises_error(
    task_manager: TaskManager,
):
    not_existing_task_id = "not_existing"

    with pytest.raises(TaskNotFoundError):
        await task_manager.push_task_stream_items(not_existing_task_id, TaskStreamItem(data="some-result"))
