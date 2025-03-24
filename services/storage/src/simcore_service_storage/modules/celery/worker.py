import logging

from celery import Celery, Task  # type: ignore[import-untyped]
from common_library.async_tools import make_async
from models_library.progress_bar import ProgressReport
from servicelib.logging_utils import log_context

from ..celery.models import TaskID

_logger = logging.getLogger(__name__)


class CeleryTaskQueueWorker:
    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app

    @make_async()
    def set_task_progress(
        self, task: Task, task_id: TaskID, report: ProgressReport
    ) -> None:
        assert task.name  # nosec
        task_name = task.name

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
