from fastapi import Request

from ...long_running_tasks._task import TasksManager


def get_tasks_manager(request: Request) -> TasksManager:
    output: TasksManager = request.app.state.long_running_task_manager
    return output
