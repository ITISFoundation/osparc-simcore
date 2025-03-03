import asyncio
import logging
import time
from collections.abc import Callable
from random import randint

import pytest
from celery import Celery, Task
from celery.contrib.abortable import AbortableTask
from models_library.progress_bar import ProgressReport
from simcore_service_storage.main import CeleryTaskQueueClient
from simcore_service_storage.modules.celery.models import TaskContext
from simcore_service_storage.modules.celery.utils import (
    get_celery_worker,
    get_event_loop,
)
from simcore_service_storage.modules.celery.worker import CeleryTaskQueueWorker
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

_logger = logging.getLogger(__name__)


async def _async_archive(
    celery_app: Celery, task_name: str, task_id: str, files: list[str]
) -> str:
    worker: CeleryTaskQueueWorker = get_celery_worker(celery_app)

    for n, file in enumerate(files, start=1):
        _logger.info("Processing file %s", file)
        worker.set_task_progress(
            task_name=task_name,
            task_id=task_id,
            report=ProgressReport(actual_value=n / len(files) * 10),
        )
        await asyncio.sleep(0.1)

    return "archive.zip"


def sync_archive(task: Task, files: list[str]) -> str:
    assert task.name
    _logger.info("Calling async_archive")
    return asyncio.run_coroutine_threadsafe(
        _async_archive(task.app, task.name, task.request.id, files),
        get_event_loop(task.app),
    ).result()


def failure_task(task: Task) -> str:
    msg = "my error here"
    raise ValueError(msg)


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
        celery_app.task(name="sync_archive", bind=True)(sync_archive)
        celery_app.task(name="failure_task", bind=True)(failure_task)
        celery_app.task(name="dreamer_task", base=AbortableTask, bind=True)(
            dreamer_task
        )

    return _


@pytest.fixture
def task_context() -> TaskContext:
    return TaskContext(user_id=1, product_name="test")


@pytest.mark.usefixtures("celery_client_app", "celery_worker_app")
async def test_sumitting_task_calling_async_function_results_with_success_state(
    celery_task_queue_client: CeleryTaskQueueClient, task_context: TaskContext
):
    task_uuid = await celery_task_queue_client.send_task(
        "sync_archive",
        task_context=task_context,
        files=[f"file{n}" for n in range(30)],
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = await celery_task_queue_client.get_task_status(
                task_context, task_uuid
            )
            assert progress.task_state == "SUCCESS"

    assert (
        await celery_task_queue_client.get_task_status(task_context, task_uuid)
    ).task_state == "SUCCESS"


@pytest.mark.usefixtures("celery_client_app", "celery_worker_app")
async def test_submitting_task_with_failure_results_with_error(
    celery_task_queue_client: CeleryTaskQueueClient,
    task_context: TaskContext,
):
    task_uuid = await celery_task_queue_client.send_task(
        "failure_task", task_context=task_context
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            result = await celery_task_queue_client.get_result(task_context, task_uuid)
            assert isinstance(result, ValueError)

    assert (
        await celery_task_queue_client.get_task_status(task_context, task_uuid)
    ).task_state == "FAILURE"
    result = await celery_task_queue_client.get_result(task_context, task_uuid)
    assert isinstance(result, ValueError)
    assert f"{result}" == "my error here"


@pytest.mark.usefixtures("celery_client_app", "celery_worker_app")
async def test_aborting_task_results_with_aborted_state(
    celery_task_queue_client: CeleryTaskQueueClient, task_context: TaskContext
):
    task_uuid = await celery_task_queue_client.send_task(
        "dreamer_task",
        task_context=task_context,
    )

    await celery_task_queue_client.abort_task(task_context, task_uuid)

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = await celery_task_queue_client.get_task_status(
                task_context, task_uuid
            )
            assert progress.task_state == "ABORTED"

    assert (
        await celery_task_queue_client.get_task_status(task_context, task_uuid)
    ).task_state == "ABORTED"
