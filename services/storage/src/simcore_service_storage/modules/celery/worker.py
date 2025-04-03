import logging

from celery import Celery  # type: ignore[import-untyped]
from models_library.progress_bar import ProgressReport
from servicelib.logging_utils import log_context

from ..celery.models import TaskID

_logger = logging.getLogger(__name__)


class CeleryTaskQueueWorker:
    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app

    def set_task_progress(
        self, task_name: str, task_id: TaskID, report: ProgressReport
    ) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Setting progress for {task_name}: {report.model_dump_json()}",
        ):
            self.celery_app.tasks[task_name].update_state(
                task_id=task_id,
                state="RUNNING",
                meta=report.model_dump(mode="json"),
            )
