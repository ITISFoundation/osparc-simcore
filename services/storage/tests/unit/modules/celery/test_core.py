import asyncio
import time
from typing import Callable

import pytest
from celery import Celery, Task
from models_library.progress_bar import ProgressReport
from simcore_service_storage.modules.celery.client.client_utils import (
    get_celery_client_interface,
)
from simcore_service_storage.modules.celery.worker.utils import (
    get_fastapi_app,
    get_loop,
    get_worker_interface,
)


async def _async_archive(
    celery_app: Celery, task_id: str, param1: int, values: list[str]
) -> str:
    fastapi_app = get_fastapi_app(celery_app)
    worker_interface = get_worker_interface(celery_app)

    worker_interface.set_progress(task_id, ProgressReport(actual_value=0))
    print(fastapi_app, task_id, param1, values)

    return "result"


def sync_archive(task: Task, param1: int, values: list[str]) -> str:
    return asyncio.run_coroutine_threadsafe(
        _async_archive(task.app, task.request.id, param1, values), get_loop(task.app)
    ).result()


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        celery_app.task(name="sync_archive", bind=True)(sync_archive)

    return _


def test_slow_task_ends_successfully(
    client_celery_app: Celery, worker_celery_app: Celery
):
    from simcore_service_storage.main import fastapi_app

    client_interface = get_celery_client_interface(fastapi_app)

    task_id = client_interface.submit(
        "sync_archive", user_id=1, param1=1, values=["a", "b"]
    )
    assert client_interface.get_state(task_id) == "PENDING"
    assert client_interface.get_result(task_id) is None

    # use tnaticyt to wait for resutl
    time.sleep(2)

    assert client_interface.get_state(task_id) == "SUCCESS"
    assert client_interface.get_result(task_id) == "result"
