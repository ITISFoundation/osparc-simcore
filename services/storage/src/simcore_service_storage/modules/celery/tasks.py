import logging
import time


from celery import Task
from common_library.errors_classes import OsparcErrorMixin
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import StorageFileID
from servicelib.logging_utils import log_context

from .utils import get_celery_worker

_logger = logging.getLogger(__name__)


def export_data(task: Task, files: list[StorageFileID]):
    _logger.info("Exporting files: %s", files)
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


class MyError(OsparcErrorMixin, Exception):
   msg_template = "Something strange happened: {msg}"


def export_data_with_error(task: Task, files: list[StorageFileID]):
    msg = "BOOM!"
    raise MyError(msg=msg)
