from celery import Celery
from models_library.progress_bar import ProgressReport

from ..models import TaskID


class CeleryWorkerInterface:
    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app

    def set_progress(
        self, task_name: str, task_id: TaskID, report: ProgressReport
    ) -> None:
        self.celery_app.tasks[task_name].update_state(
            task_id=task_id,
            state="PROGRESS",
            meta=report.model_dump(mode="json"),
        )
