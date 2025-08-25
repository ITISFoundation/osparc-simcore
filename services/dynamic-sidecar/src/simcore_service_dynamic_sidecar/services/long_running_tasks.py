from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks.server import (
    get_long_running_manager_from_app,
)


async def cleanup_long_running_tasks(app: FastAPI) -> None:
    manager = get_long_running_manager_from_app(app)
    await manager.tasks_manager.remove_local_running_tasks()
