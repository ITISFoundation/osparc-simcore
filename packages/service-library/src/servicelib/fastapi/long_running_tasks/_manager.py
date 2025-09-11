from fastapi import Request

from ...long_running_tasks.manager import LongRunningManager
from ...long_running_tasks.models import TaskContext


class FastAPILongRunningManager(LongRunningManager):
    @staticmethod
    def get_task_context(request: Request) -> TaskContext:
        _ = request
        return {}
