import logging
from collections.abc import Callable

from celery import Celery
from celery.contrib.abortable import AbortableTask
from models_library.progress_bar import ProgressReport
from servicelib.logging_utils import log_context

from .models import TaskID, TaskState

_logger = logging.getLogger(__name__)


class CeleryTaskQueueWorker:
    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app

    def register_task(self, fn: Callable, task_name: str | None = None) -> None:
        name = task_name or fn.__name__
        with log_context(_logger, logging.INFO, msg=f"Registering {name} task"):
            self.celery_app.task(name=name, base=AbortableTask, bind=True)(fn)

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
                state=TaskState.PROGRESS.value,
                meta=report.model_dump(mode="json"),
            )
