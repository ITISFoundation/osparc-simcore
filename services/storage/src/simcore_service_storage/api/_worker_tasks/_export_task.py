import asyncio
import logging

from celery import Task  # type: ignore[import-untyped]
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import StorageFileID
from servicelib.logging_utils import log_context

from ...modules.celery.utils import get_celery_worker

_logger = logging.getLogger(__name__)


async def export_data(task: Task, files: list[StorageFileID]):
    await get_celery_worker(task.app).set_task_progress(
        task, ProgressReport(actual_value=0.1)
    )

    _logger.info("Exporting files: %s", files)
    for n, file in enumerate(files, start=1):
        with log_context(
            _logger,
            logging.INFO,
            msg=f"Exporting {file=} ({n}/{len(files)})",
        ):
            assert task.name
            await get_celery_worker(task.app).set_task_progress(
                task, ProgressReport(actual_value=n / len(files) * 100)
            )
            await asyncio.sleep(10)
    return "done"
