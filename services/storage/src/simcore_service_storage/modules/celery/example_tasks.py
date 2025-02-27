import asyncio
import logging

from celery import Celery, Task
from models_library.progress_bar import ProgressReport

from .utils import get_celery_worker, get_event_loop
from .worker import CeleryTaskQueueWorker

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
