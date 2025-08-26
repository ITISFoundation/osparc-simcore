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
from celery import Celery, Task
from celery.contrib.abortable import AbortableTask
from celery_library.errors import TransferrableCeleryError
from celery_library.task import register_task
from celery_library.task_manager import CeleryTaskManager
from celery_library.utils import get_app_server
from common_library.errors_classes import OsparcErrorMixin
from models_library.progress_bar import ProgressReport
from servicelib.celery.models import (
    TaskFilter,
    TaskID,
    TaskMetadata,
    TaskState,
)
from servicelib.logging_utils import log_context
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

_logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = ["redis"]
pytest_simcore_ops_services_selection = []


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


async def dreamer_task(task: AbortableTask, task_id: TaskID) -> list[int]:
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
    celery_task_manager: CeleryTaskManager,
):
    task_filter = TaskFilter(user_id=42)

    task_uuid = await celery_task_manager.submit_task(
        TaskMetadata(
            name=fake_file_processor.__name__,
        ),
        task_filter=task_filter,
        files=[f"file{n}" for n in range(5)],
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            status = await celery_task_manager.get_task_status(task_filter, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    assert (
        await celery_task_manager.get_task_status(task_filter, task_uuid)
    ).task_state == TaskState.SUCCESS
    assert (
        await celery_task_manager.get_task_result(task_filter, task_uuid)
    ) == "archive.zip"


async def test_submitting_task_with_failure_results_with_error(
    celery_task_manager: CeleryTaskManager,
):
    task_filter = TaskFilter(user_id=42)

    task_uuid = await celery_task_manager.submit_task(
        TaskMetadata(
            name=failure_task.__name__,
        ),
        task_filter=task_filter,
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):

        with attempt:
            raw_result = await celery_task_manager.get_task_result(
                task_filter, task_uuid
            )
            assert isinstance(raw_result, TransferrableCeleryError)

    raw_result = await celery_task_manager.get_task_result(task_filter, task_uuid)
    assert f"{raw_result}" == "Something strange happened: BOOM!"


async def test_cancelling_a_running_task_aborts_and_deletes(
    celery_task_manager: CeleryTaskManager,
):
    task_filter = TaskFilter(user_id=42)

    task_uuid = await celery_task_manager.submit_task(
        TaskMetadata(
            name=dreamer_task.__name__,
        ),
        task_filter=task_filter,
    )

    await asyncio.sleep(3.0)

    await celery_task_manager.cancel_task(task_filter, task_uuid)

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = await celery_task_manager.get_task_status(task_filter, task_uuid)
            assert progress.task_state == TaskState.ABORTED

    assert (
        await celery_task_manager.get_task_status(task_filter, task_uuid)
    ).task_state == TaskState.ABORTED

    assert task_uuid not in await celery_task_manager.list_tasks(task_filter)


async def test_listing_task_uuids_contains_submitted_task(
    celery_task_manager: CeleryTaskManager,
):
    task_filter = TaskFilter(user_id=42)

    task_uuid = await celery_task_manager.submit_task(
        TaskMetadata(
            name=dreamer_task.__name__,
        ),
        task_filter=task_filter,
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
    ):
        with attempt:
            tasks = await celery_task_manager.list_tasks(task_filter)
            assert any(task.uuid == task_uuid for task in tasks)

        tasks = await celery_task_manager.list_tasks(task_filter)
        assert any(task.uuid == task_uuid for task in tasks)
