import asyncio
from typing import Callable

import pytest
from celery import Celery, Task
from models_library.progress_bar import ProgressReport
from simcore_service_storage.main import fastapi_app
from simcore_service_storage.modules.celery.client._interface import TaskIdComponents
from simcore_service_storage.modules.celery.client.client_utils import (
    get_celery_client_interface,
)
from simcore_service_storage.modules.celery.worker.utils import (
    get_loop,
    get_worker_interface,
)
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed


async def _async_archive(
    celery_app: Celery, task_name: str, task_id: str, files: list[str]
) -> str:
    worker_interface = get_worker_interface(celery_app)

    for n in range(len(files)):
        worker_interface.set_progress(
            task_name=task_name,
            task_id=task_id,
            report=ProgressReport(actual_value=n / len(files) * 100),
        )
        await asyncio.sleep(0.1)

    return "archive.zip"


def sync_archive(task: Task, files: list[str]) -> str:
    assert task.name
    return asyncio.run_coroutine_threadsafe(
        _async_archive(task.app, task.name, task.request.id, files), get_loop(task.app)
    ).result()


def sync_error(task: Task) -> str:
    raise ValueError("my error here")


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        celery_app.task(name="sync_archive", bind=True)(sync_archive)
        celery_app.task(name="sync_error", bind=True)(sync_error)

    return _


def test_archive(
    client_celery_app: Celery,
    worker_celery_app: Celery,
):
    client_interface = get_celery_client_interface(fastapi_app)

    task_id_components = TaskIdComponents(user_id=1)

    task_id = client_interface.submit(
        "sync_archive",
        task_id_components=task_id_components,
        files=[f"file{n}" for n in range(100)],
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            progress = client_interface.get_progress(task_id)
            assert progress.task_state == "SUCCESS"

    assert client_interface.get_progress(task_id).task_state == "SUCCESS"


def test_sync_error(
    client_celery_app: Celery,
    worker_celery_app: Celery,
):
    client_interface = get_celery_client_interface(fastapi_app)

    task_id = client_interface.submit(
        "sync_error", task_id_components=TaskIdComponents(user_id=1)
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError), wait=wait_fixed(1)
    ):
        with attempt:
            result = client_interface.get_result(task_id)
            assert isinstance(result, ValueError)

    assert f"{client_interface.get_result(task_id)}" == "my error here"
