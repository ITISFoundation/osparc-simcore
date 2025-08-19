from fastapi import Request

from ...long_running_tasks.base_long_running_manager import BaseLongRunningManager
from ...long_running_tasks.models import TaskContext


class FastAPILongRunningManager(BaseLongRunningManager):
    @staticmethod
    def get_task_context(request: Request) -> TaskContext:
        _ = request
        return {}
