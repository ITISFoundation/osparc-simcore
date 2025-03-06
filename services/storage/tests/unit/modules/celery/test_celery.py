import asyncio
import logging
import time
from collections.abc import Callable
from random import randint

from pydantic import TypeAdapter, ValidationError
import pytest
from celery import Celery, Task
from celery.contrib.abortable import AbortableTask
from common_library.errors_classes import OsparcErrorMixin
from models_library.progress_bar import ProgressReport
from servicelib.logging_utils import log_context
from simcore_service_storage.modules.celery import get_event_loop
from simcore_service_storage.modules.celery._common import define_task
from simcore_service_storage.modules.celery.client import CeleryTaskQueueClient
from simcore_service_storage.modules.celery.models import TaskContext, TaskError, TaskState
from simcore_service_storage.modules.celery.utils import (
    get_celery_worker,
    get_fastapi_app,
)
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

_logger = logging.getLogger(__name__)


async def _async_archive(
    celery_app: Celery, task_name: str, task_id: str, files: list[str]
) -> str:
    worker = get_celery_worker(celery_app)

    def sleep_for(seconds: float) -> None:
        time.sleep(seconds)

    for n, file in enumerate(files, start=1):
        with log_context(_logger, logging.INFO, msg=f"Processing file {file}"):
            worker.set_task_progress(
                task_name=task_name,
                task_id=task_id,
                report=ProgressReport(actual_value=n / len(files) * 10),
            )
            await asyncio.get_event_loop().run_in_executor(None, sleep_for, 1)

    return "archive.zip"


def sync_archive(task: Task, files: list[str]) -> str:
    assert task.name
    _logger.info("Calling async_archive")
    return asyncio.run_coroutine_threadsafe(
        _async_archive(task.app, task.name, task.request.id, files),
        get_event_loop(get_fastapi_app(task.app)),
    ).result()


class MyError(OsparcErrorMixin, Exception):
   msg_template = "Something strange happened: {msg}"


def failure_task(task: Task):
    msg = "BOOM!"
    raise MyError(msg=msg)


def dreamer_task(task: AbortableTask) -> list[int]:
    numbers = []
    for _ in range(30):
        if task.is_aborted():
            _logger.warning("Alarm clock")
            return numbers
        numbers.append(randint(1, 90))
        time.sleep(1)
    return numbers


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        define_task(celery_app, sync_archive)
        define_task(celery_app, failure_task)
        define_task(celery_app, dreamer_task)

    return _


@pytest.mark.usefixtures("celery_worker")
async def test_sumitting_task_calling_async_function_results_with_success_state(
    celery_client: CeleryTaskQueueClient,
):
    task_context = TaskContext(user_id=42)

    task_uuid = await celery_client.send_task(
        "sync_archive",
        task_context=task_context,
        files=[f"file{n}" for n in range(5)],
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            status = await celery_client.get_task_status(task_context, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    assert (
        await celery_client.get_task_result(task_context, task_uuid)
    ) == "archive.zip"
    assert (
        await celery_client.get_task_status(task_context, task_uuid)
    ).task_state == TaskState.SUCCESS
    assert (
        await celery_client.get_task_result(task_context, task_uuid)
    ) == "archive.zip"


@pytest.mark.usefixtures("celery_worker")
async def test_submitting_task_with_failure_results_with_error(
    celery_client: CeleryTaskQueueClient,
):
    task_context = TaskContext(user_id=42)

    task_uuid = await celery_client.send_task("failure_task", task_context=task_context)

    for attempt in Retrying(
        retry=retry_if_exception_type((AssertionError, ValidationError)),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            raw_result = await celery_client.get_task_result(task_context, task_uuid)
            result = TypeAdapter(TaskError).validate_python(raw_result)
            assert isinstance(result, TaskError)

    assert (
        await celery_client.get_task_status(task_context, task_uuid)
    ).task_state == TaskState.ERROR
    raw_result = await celery_client.get_task_result(task_context, task_uuid)
    result = TypeAdapter(TaskError).validate_python(raw_result)
    assert f"{result.exc_msg}" == "Something strange happened: BOOM!"


@pytest.mark.usefixtures("celery_worker")
async def test_aborting_task_results_with_aborted_state(
    celery_client: CeleryTaskQueueClient,
):
    task_context = TaskContext(user_id=42)

    task_uuid = await celery_client.send_task(
        "dreamer_task",
        task_context=task_context,
    )

    await celery_client.abort_task(task_context, task_uuid)

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = await celery_client.get_task_status(task_context, task_uuid)
            assert progress.task_state == TaskState.ABORTED

    assert (
        await celery_client.get_task_status(task_context, task_uuid)
    ).task_state == TaskState.ABORTED
