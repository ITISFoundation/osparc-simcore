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
    TaskKey,
    TaskState,
    TaskUUID,
    Wildcard,
)
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

_faker = Faker()

_logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = ["redis"]
pytest_simcore_ops_services_selection = []


class MyOwnerMetadata(OwnerMetadata):
    user_id: int


async def _fake_file_processor(
    celery_app: Celery, task_name: str, task_key: str, files: list[str]
) -> str:
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


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        register_task(celery_app, fake_file_processor)
        register_task(celery_app, failure_task)
        register_task(celery_app, dreamer_task)

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

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            status = await task_manager.get_task_status(owner_metadata, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    assert (
        await task_manager.get_task_status(owner_metadata, task_uuid)
    ).task_state == TaskState.SUCCESS
    assert (
        await task_manager.get_task_result(owner_metadata, task_uuid)
    ) == "archive.zip"


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

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):

        with attempt:
            raw_result = await task_manager.get_task_result(owner_metadata, task_uuid)
            assert isinstance(raw_result, TransferrableCeleryError)

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

    assert task_uuid not in await task_manager.list_tasks(owner_metadata)


async def test_listing_task_uuids_contains_submitted_task(
    task_manager: CeleryTaskManager,
    with_celery_worker: WorkController,
):

    owner_metadata = MyOwnerMetadata(user_id=42, owner="test-owner")

    task_uuid = await task_manager.submit_task(
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
            owner_metadata = MyOwnerMetadata(
                user_id=user_id, product_name=_faker.word(), owner=_owner
            )
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
