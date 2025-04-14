import logging
from dataclasses import dataclass

from models_library.progress_bar import ProgressReport

from ..celery.models import TaskID, TaskInfoStore

_logger = logging.getLogger(__name__)


@dataclass
class CeleryTaskWorker:
    _task_info_store: TaskInfoStore

    async def set_progress(self, task_id: TaskID, report: ProgressReport) -> None:
        await self._task_info_store.set_progress(
            task_id=task_id,
            report=report,
        )
