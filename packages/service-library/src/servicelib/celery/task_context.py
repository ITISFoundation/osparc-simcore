from dataclasses import dataclass

from models_library.celery import TaskID, TaskName

from .app_server import BaseAppServer


@dataclass(frozen=True, slots=True)
class TaskContext:
    id: TaskID
    name: TaskName
    app_server: BaseAppServer
    user_id: int | None = None
    product_name: str | None = None
