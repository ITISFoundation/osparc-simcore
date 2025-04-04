import logging

from celery import Celery  # type: ignore[import-untyped]
from servicelib.logging_utils import log_context

from ...modules.celery._celery_types import register_celery_types
from ...modules.celery._task import register_task
from ._files import complete_upload_file
from ._paths import compute_path_size, delete_paths
from ._simcore_s3 import deep_copy_files_from_project, export_data

_logger = logging.getLogger(__name__)


def setup_worker_tasks(app: Celery) -> None:
    register_celery_types()
    with log_context(_logger, logging.INFO, msg="worker task registration"):
        register_task(app, export_data)
        register_task(app, compute_path_size)
        register_task(app, complete_upload_file)
        register_task(app, delete_paths)
        register_task(app, deep_copy_files_from_project)
