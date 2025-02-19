from celery import Celery
from models_library.progress_bar import ProgressReport

from ..models import TaskID


class CeleryWorkerInterface:
    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app

    def set_progress(self, task_id: TaskID, report: ProgressReport) -> None:
        pass
