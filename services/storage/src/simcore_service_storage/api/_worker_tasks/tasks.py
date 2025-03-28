import logging

from celery import Celery  # type: ignore[import-untyped]
from servicelib.logging_utils import log_context

from ...modules.celery._celery_types import register_celery_types
from ...modules.celery._task import define_task
from ._files import complete_upload_file
from ._paths import compute_path_size
from ._simcore_s3 import data_export, deep_copy_files_from_project

_logger = logging.getLogger(__name__)


def setup_worker_tasks(app: Celery) -> None:
    register_celery_types()
    with log_context(
        _logger,
        logging.INFO,
        msg="Storage setup Worker Tasks",
    ):
        define_task(app, data_export)
        define_task(app, compute_path_size)
        define_task(app, complete_upload_file)
        define_task(app, deep_copy_files_from_project)
