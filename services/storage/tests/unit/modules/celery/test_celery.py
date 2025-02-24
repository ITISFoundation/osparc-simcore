import logging
import time
from random import randint
from typing import Callable

import pytest
from celery import Celery, Task
from celery.contrib.abortable import AbortableTask
from simcore_service_storage.main import fastapi_app
from simcore_service_storage.modules.celery.client import get_client
from simcore_service_storage.modules.celery.example_tasks import sync_archive
from simcore_service_storage.modules.celery.models import TaskIDParts
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


def test_archive(
    client_celery_app: Celery,
    worker_celery_app: Celery,
):
    client = get_client(fastapi_app)

    task_id_parts = TaskIDParts(user_id=1)

    task_id = client.submit(
        "sync_archive",
        task_id_parts=task_id_parts,
        files=[f"file{n}" for n in range(100)],
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = client.get_status(task_id)
            assert progress.task_state == "SUCCESS"

    assert client.get_status(task_id).task_state == "SUCCESS"


def test_failure_task(
    client_celery_app: Celery,
    worker_celery_app: Celery,
):
    client = get_client(fastapi_app)

    task_id = client.submit("failure_task", task_id_parts=TaskIDParts(user_id=1))

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
    ):
        with attempt:
            result = client.get_result(task_id)
            assert isinstance(result, ValueError)

    assert client.get_status(task_id).task_state == "FAILURE"
    assert f"{client.get_result(task_id)}" == "my error here"


def test_dreamer_task(
    client_celery_app: Celery,
    worker_celery_app: Celery,
):
    client = get_client(fastapi_app)

    task_id = client.submit("dreamer_task", task_id_parts=TaskIDParts(user_id=1))

    time.sleep(1)

    client.cancel(task_id)

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = client.get_status(task_id)
            assert progress.task_state == "ABORTED"

    assert client.get_status(task_id).task_state == "ABORTED"
