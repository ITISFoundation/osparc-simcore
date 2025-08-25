from fastapi import Request

from ...long_running_tasks.models import TaskContext
from ...long_running_tasks.server_long_running_manager import ServerLongRunningManager


class FastAPILongRunningManager(ServerLongRunningManager):
    @staticmethod
    def get_task_context(request: Request) -> TaskContext:
        _ = request
        return {}
