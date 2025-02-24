import logging
from typing import Callable

from celery import Celery
from models_library.progress_bar import ProgressReport

from ..models import TaskID

_logger = logging.getLogger(__name__)


class CeleryWorkerInterface:
    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app

    def register_task(self, fn: Callable):
        _logger.info("Registering %s task", fn.__name__)
        self.celery_app.task(name=fn.__name__, bind=True)(fn)

    def set_progress(
        self, task_name: str, task_id: TaskID, report: ProgressReport
    ) -> None:
        self.celery_app.tasks[task_name].update_state(
            task_id=task_id,
            state="PROGRESS",
            meta=report.model_dump(mode="json"),
        )
