from dataclasses import dataclass

from models_library.celery import TaskID

from .app_server import BaseAppServer


@dataclass(frozen=True, slots=True)
class TaskContext:
    """Framework-agnostic context passed to async tasks registered via ``register_task``.

    Decouples user task code from the underlying Celery ``Task`` object.
    """

    id: TaskID
    name: str
    app_server: BaseAppServer
