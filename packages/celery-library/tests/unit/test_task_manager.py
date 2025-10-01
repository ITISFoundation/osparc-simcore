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
from celery_library.errors import TaskNotFoundError, TransferrableCeleryError
from celery_library.task import register_task
from celery_library.task_manager import CeleryTaskManager
from celery_library.utils import get_app_server
from common_library.errors_classes import OsparcErrorMixin
from faker import Faker
from models_library.progress_bar import ProgressReport
from servicelib.celery.models import (
    ExecutionMetadata,
    OwnerMetadata,
    TaskDataEvent,
    TaskEventType,
    TaskID,
    TaskState,
    TaskStatusEvent,
    TaskStatusValue,
    TaskUUID,
    Wildcard,
)
from servicelib.logging_utils import log_context
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

_faker = Faker()

_logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = ["redis"]
pytest_simcore_ops_services_selection = []


class MyOwnerMetadata(OwnerMetadata):
    user_id: int


async def _fake_file_processor(
    celery_app: Celery, task_name: str, task_id: str, files: list[str]
) -> str:
    def sleep_for(seconds: float) -> None:
        time.sleep(seconds)

    for n, file in enumerate(files, start=1):
        with log_context(_logger, logging.INFO, msg=f"Processing file {file}"):
            await get_app_server(celery_app).task_manager.set_task_progress(
                task_id=task_id,
                report=ProgressReport(actual_value=n / len(files)),
            )
            await asyncio.get_event_loop().run_in_executor(None, sleep_for, 1)

    return "archive.zip"


def fake_file_processor(task: Task, task_id: TaskID, files: list[str]) -> str:
    assert task_id
    assert task.name
    _logger.info("Calling _fake_file_processor")
    return asyncio.run_coroutine_threadsafe(
        _fake_file_processor(task.app, task.name, task.request.id, files),
        get_app_server(task.app).event_loop,
    ).result()


class MyError(OsparcErrorMixin, Exception):
    msg_template = "Something strange happened: {msg}"


def failure_task(task: Task, task_id: TaskID) -> None:
    assert task_id
    assert task
    msg = "BOOM!"
    raise MyError(msg=msg)


async def dreamer_task(task: Task, task_id: TaskID) -> list[int]:
    numbers = []
    for _ in range(30):
        numbers.append(randint(1, 90))  # noqa: S311
        await asyncio.sleep(0.5)
    return numbers


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        register_task(celery_app, fake_file_processor)
        register_task(celery_app, failure_task)
        register_task(celery_app, dreamer_task)

    return _


@pytest.mark.usefixtures("with_celery_worker")
async def test_submitting_task_calling_async_function_results_with_success_state(
    celery_task_manager: CeleryTaskManager,
):

    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await celery_task_manager.submit_task(
        ExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner_metadata=owner_metadata,
        files=[f"file{n}" for n in range(5)],
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            status = await celery_task_manager.get_task_status(
                owner_metadata, task_uuid
            )
            assert status.task_state == TaskState.SUCCESS

    assert (
        await celery_task_manager.get_task_status(owner_metadata, task_uuid)
    ).task_state == TaskState.SUCCESS
    assert (
        await celery_task_manager.get_task_result(owner_metadata, task_uuid)
    ) == "archive.zip"


@pytest.mark.usefixtures("with_celery_worker")
async def test_submitting_task_with_failure_results_with_error(
    celery_task_manager: CeleryTaskManager,
):

    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await celery_task_manager.submit_task(
        ExecutionMetadata(
            name=failure_task.__name__,
        ),
        owner_metadata=owner_metadata,
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):

        with attempt:
            raw_result = await celery_task_manager.get_task_result(
                owner_metadata, task_uuid
            )
            assert isinstance(raw_result, TransferrableCeleryError)

    raw_result = await celery_task_manager.get_task_result(owner_metadata, task_uuid)
    assert f"{raw_result}" == "Something strange happened: BOOM!"


@pytest.mark.usefixtures("with_celery_worker")
async def test_cancelling_a_running_task_aborts_and_deletes(
    celery_task_manager: CeleryTaskManager,
):

    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await celery_task_manager.submit_task(
        ExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner_metadata=owner_metadata,
    )

    await asyncio.sleep(3.0)

    await celery_task_manager.cancel_task(owner_metadata, task_uuid)

    with pytest.raises(TaskNotFoundError):
        await celery_task_manager.get_task_status(owner_metadata, task_uuid)

    assert task_uuid not in await celery_task_manager.list_tasks(owner_metadata)


@pytest.mark.usefixtures("with_celery_worker")
async def test_listing_task_uuids_contains_submitted_task(
    celery_task_manager: CeleryTaskManager,
):

    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await celery_task_manager.submit_task(
        ExecutionMetadata(
            name=dreamer_task.__name__,
        ),
        owner_metadata=owner_metadata,
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
    ):
        with attempt:
            tasks = await celery_task_manager.list_tasks(owner_metadata)
            assert any(task.uuid == task_uuid for task in tasks)

    tasks = await celery_task_manager.list_tasks(owner_metadata)
    assert any(task.uuid == task_uuid for task in tasks)


@pytest.mark.usefixtures("with_celery_worker")
async def test_filtering_listing_tasks(
    celery_task_manager: CeleryTaskManager,
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
            owner_metadata = MyOwnerMetadata(
                user_id=user_id, product_name=_faker.word(), owner=_owner
            )
            task_uuid = await celery_task_manager.submit_task(
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
            task_uuid = await celery_task_manager.submit_task(
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
        tasks = await celery_task_manager.list_tasks(search_owner_metadata)
        assert expected_task_uuids == {task.uuid for task in tasks}
    finally:
        # clean up all tasks. this should ideally be done in the fixture
        for task_uuid, owner_metadata in all_tasks:
            await celery_task_manager.cancel_task(owner_metadata, task_uuid)


@pytest.mark.usefixtures("with_celery_worker")
async def test_publish_task_event_creates_data_event(
    celery_task_manager: CeleryTaskManager,
):
    """Test that publishing a data event works correctly."""
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    # Create a task first
    task_uuid = await celery_task_manager.submit_task(
        ExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner_metadata=owner_metadata,
        files=[f"file{n}" for n in range(2)],
    )

    # Create and publish a data event
    task_id = owner_metadata.model_dump_task_id(task_uuid=task_uuid)
    data_event = TaskDataEvent(data={"progress": 0.5, "message": "Processing..."})

    # This should not raise an exception
    await celery_task_manager.publish_task_event(task_id, data_event)

    # Clean up
    await celery_task_manager.cancel_task(owner_metadata, task_uuid)


@pytest.mark.usefixtures("with_celery_worker")
async def test_publish_task_event_creates_status_event(
    celery_task_manager: CeleryTaskManager,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await celery_task_manager.submit_task(
        ExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner_metadata=owner_metadata,
        files=[f"file{n}" for n in range(2)],
    )

    task_id = owner_metadata.model_dump_task_id(task_uuid=task_uuid)
    status_event = TaskStatusEvent(data=TaskStatusValue.SUCCESS)

    await celery_task_manager.publish_task_event(task_id, status_event)

    await celery_task_manager.cancel_task(owner_metadata, task_uuid)


@pytest.mark.usefixtures("with_celery_worker")
async def test_consume_task_events_reads_published_events(
    celery_task_manager: CeleryTaskManager,
):
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await celery_task_manager.submit_task(
        ExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner_metadata=owner_metadata,
        files=[f"file{n}" for n in range(2)],
    )

    task_id = owner_metadata.model_dump_task_id(task_uuid=task_uuid)

    data_event = TaskDataEvent(data={"progress": 0.3, "message": "Starting..."})
    status_event = TaskStatusEvent(data=TaskStatusValue.SUCCESS)

    await celery_task_manager.publish_task_event(task_id, data_event)
    await celery_task_manager.publish_task_event(task_id, status_event)

    # Consume events
    events_received = []
    async for event_id, event in celery_task_manager.consume_task_events(
        owner_metadata=owner_metadata,
        task_uuid=task_uuid,
    ):
        events_received.append((event_id, event))
        if len(events_received) >= 2:
            break

    assert len(events_received) >= 1

    data_events = [
        event for _, event in events_received if event.type == TaskEventType.DATA
    ]
    status_events = [
        event for _, event in events_received if event.type == TaskEventType.STATUS
    ]

    assert len(data_events) >= 1
    assert data_events[0].data == {"progress": 0.3, "message": "Starting..."}

    success_events = [
        event for event in status_events if event.data == TaskStatusValue.SUCCESS
    ]
    assert len(success_events) >= 1

    await celery_task_manager.cancel_task(owner_metadata, task_uuid)


@pytest.mark.usefixtures("with_celery_worker")
async def test_consume_task_events_with_last_id_filters_correctly(
    celery_task_manager: CeleryTaskManager,
):
    """Test that consuming task events with last_id parameter works correctly."""
    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await celery_task_manager.submit_task(
        ExecutionMetadata(
            name=fake_file_processor.__name__,
        ),
        owner_metadata=owner_metadata,
        files=[f"file{n}" for n in range(2)],
    )

    task_id = owner_metadata.model_dump_task_id(task_uuid=task_uuid)
    first_event = TaskDataEvent(data={"progress": 0.1, "message": "First event"})
    await celery_task_manager.publish_task_event(task_id, first_event)

    first_event_id = None
    async for event_id, event in celery_task_manager.consume_task_events(
        owner_metadata=owner_metadata,
        task_uuid=task_uuid,
    ):
        if (
            event.type == TaskEventType.DATA
            and event.data.get("message") == "First event"
        ):
            first_event_id = event_id
            break

    assert first_event_id is not None

    second_event = TaskDataEvent(data={"progress": 0.5, "message": "Second event"})
    await celery_task_manager.publish_task_event(task_id, second_event)

    events_after_first = []
    async for event_id, event in celery_task_manager.consume_task_events(
        owner_metadata=owner_metadata,
        task_uuid=task_uuid,
        last_id=first_event_id,
    ):
        events_after_first.append((event_id, event))
        if (
            event.type == TaskEventType.DATA
            and event.data.get("message") == "Second event"
        ):
            break

    assert len(events_after_first) >= 1
    data_events_after = [
        event for _, event in events_after_first if event.type == TaskEventType.DATA
    ]

    first_event_messages = [
        event.data.get("message")
        for event in data_events_after
        if event.data.get("message") == "First event"
    ]
    assert len(first_event_messages) == 0

    second_event_messages = [
        event.data.get("message")
        for event in data_events_after
        if event.data.get("message") == "Second event"
    ]
    assert len(second_event_messages) >= 1

    await celery_task_manager.cancel_task(owner_metadata, task_uuid)
