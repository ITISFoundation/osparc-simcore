import pytest
from celery import Celery, Task
from fastapi import FastAPI
from models_library.progress_bar import ProgressReport
from pytest_mock import MockerFixture
from simcore_service_storage.modules.celery.utils import (
    set_celery_worker_client,
    set_fastapi_app,
)
from simcore_service_storage.modules.celery.worker import CeleryWorkerClient


@pytest.fixture
def fake_celery_task(celery_app: Celery, initialized_app: FastAPI) -> Task:
    celery_task = Task()
    celery_task.app = celery_app
    set_fastapi_app(celery_app, initialized_app)
    set_celery_worker_client(celery_app, CeleryWorkerClient(celery_app))
    return celery_task


@pytest.fixture
def mock_task_progress(mocker: MockerFixture) -> list[ProgressReport]:
    progress_updates = []

    async def _progress(*args, **_) -> None:
        progress_updates.append(args[1])

    mocker.patch(
        "simcore_service_storage.modules.celery.worker.CeleryWorkerClient.set_task_progress",
        side_effect=_progress,
    )
    return progress_updates
