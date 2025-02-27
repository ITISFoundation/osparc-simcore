import logging
import time
from collections.abc import Callable
from random import randint

import pytest
from celery import Celery, Task
from celery.contrib.abortable import AbortableTask
from simcore_service_storage.main import CeleryTaskQueueClient
from simcore_service_storage.modules.celery.example_tasks import sync_archive
from simcore_service_storage.modules.celery.models import TaskContext
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

_logger = logging.getLogger(__name__)


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


@pytest.mark.usefixtures("celery_client_app", "celery_worker_app")
async def test_sumitting_task_calling_async_function_results_with_success_state(
    celery_task_queue_client: CeleryTaskQueueClient,
):
    task_context = TaskContext(user_id=1, product_name="test")

    task_id = await celery_task_queue_client.send_task(
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
            progress = await celery_task_queue_client.get_task_status(task_id)
            assert progress.task_state == "SUCCESS"

    assert (
        await celery_task_queue_client.get_task_status(task_id)
    ).task_state == "SUCCESS"


@pytest.mark.usefixtures("celery_client_app", "celery_worker_app")
async def test_submitting_task_with_failure_results_with_error(
    celery_task_queue_client: CeleryTaskQueueClient,
):
    task_id = await celery_task_queue_client.send_task(
        "failure_task",
        task_context=TaskContext(user_id=1, product_name="test"),
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
    ):
        with attempt:
            result = await celery_task_queue_client.get_result(task_id)
            assert isinstance(result, ValueError)

    assert (
        await celery_task_queue_client.get_task_status(task_id)
    ).task_state == "FAILURE"
    result = await celery_task_queue_client.get_result(task_id)
    assert isinstance(result, ValueError)
    assert f"{result}" == "my error here"


@pytest.mark.usefixtures("celery_client_app", "celery_worker_app")
async def test_aborting_task_results_with_aborted_state(
    celery_task_queue_client: CeleryTaskQueueClient,
):
    task_id = await celery_task_queue_client.send_task(
        "dreamer_task",
        task_context=TaskContext(user_id=1, product_name="test"),
    )

    await celery_task_queue_client.abort_task(task_id)

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = await celery_task_queue_client.get_task_status(task_id)
            assert progress.task_state == "ABORTED"

    assert (
        await celery_task_queue_client.get_task_status(task_id)
    ).task_state == "ABORTED"
