import asyncio
import logging

from celery import Celery, Task
from models_library.progress_bar import ProgressReport

from .worker.utils import get_loop, get_worker_interface

_logger = logging.getLogger(__name__)


async def _async_archive(
    celery_app: Celery, task_name: str, task_id: str, files: list[str]
) -> str:
    print("am I being executed?")
    worker_interface = get_worker_interface(celery_app)

    for n in range(len(files)):
        _logger.error("Progressing %d", n)
        worker_interface.set_progress(
            task_name=task_name,
            task_id=task_id,
            report=ProgressReport(actual_value=n / len(files) * 10),
        )
        await asyncio.sleep(0.1)

    _logger.error("execution completed")
    return "archive.zip"


def sync_archive(task: Task, files: list[str]) -> str:
    print("getting new task")
    assert task.name
    _logger.info("Calling async_archive")
    return asyncio.run_coroutine_threadsafe(
        _async_archive(task.app, task.name, task.request.id, files), get_loop(task.app)
    ).result()
