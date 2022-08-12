from fastapi import Request

from ...long_running_tasks._task import TasksManager


def get_tasks_manager(request: Request) -> TasksManager:
    return request.app.state.long_running_task_manager
