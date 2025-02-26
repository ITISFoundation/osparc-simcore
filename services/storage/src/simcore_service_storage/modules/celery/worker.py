import logging
from collections.abc import Callable

from celery import Celery
from celery.contrib.abortable import AbortableTask
from models_library.progress_bar import ProgressReport

from .models import TaskID

_logger = logging.getLogger(__name__)


class CeleryTaskQueueWorker:
    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app

    def register_task(self, fn: Callable):
        _logger.debug("Registering %s task", fn.__name__)
        self.celery_app.task(name=fn.__name__, base=AbortableTask, bind=True)(fn)

    def set_progress(
        self, task_name: str, task_id: TaskID, report: ProgressReport
    ) -> None:
        _logger.debug(
            "Setting progress for %s: %s", task_name, report.model_dump_json()
        )
        self.celery_app.tasks[task_name].update_state(
            task_id=task_id,
            state="PROGRESS",
            meta=report.model_dump(mode="json"),
        )
