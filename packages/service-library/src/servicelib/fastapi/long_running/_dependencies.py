from fastapi import Request
from ._task import TaskManager


def get_task_manager(request: Request) -> TaskManager:
    return request.app.state.long_running_task_manager
