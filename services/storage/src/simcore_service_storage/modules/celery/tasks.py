import logging
import time

from celery import Task
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import StorageFileID
from servicelib.logging_utils import log_context
from simcore_service_storage.modules.celery.utils import get_celery_worker

_logger = logging.getLogger(__name__)


def export_data(task: Task, files: list[StorageFileID]):
    for n, file in enumerate(files, start=1):
        with log_context(
            _logger,
            logging.INFO,
            msg=f"Exporting {file=} ({n}/{len(files)})",
        ):
            assert task.name
            get_celery_worker(task.app).set_task_progress(
                task_name=task.name,
                task_id=task.request.id,
                report=ProgressReport(actual_value=n / len(files) * 100),
            )
            time.sleep(10)
    return "done"
