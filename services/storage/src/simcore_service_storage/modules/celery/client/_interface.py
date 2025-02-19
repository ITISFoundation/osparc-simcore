from typing import Any
from uuid import uuid4

from celery import Celery
from celery.result import AsyncResult
from models_library.users import UserID

from ..models import TaskID


class CeleryClientInterface:
    def __init__(self, celery_app: Celery):
        self._celery_app = celery_app

    def submit(self, name: str, *, user_id: UserID, **kwargs) -> TaskID:
        task_id = f"{user_id}_{name}_{uuid4()}"
        return self._celery_app.send_task(name, task_id=task_id, kwargs=kwargs).id

    def _get_result(self, task_id: TaskID) -> AsyncResult:
        return self._celery_app.AsyncResult(task_id)

    def get_state(self, task_id: TaskID) -> str:
        # task_id , state, progress
        return self._get_result(task_id).state

    def get_result(self, task_id: TaskID) -> Any:
        return self._get_result(task_id).result

    def cancel(self, task_id: TaskID) -> None:
        self._celery_app.control.revoke(task_id, terminate=True)

    def list(self, user_id: UserID) -> list[TaskID]:
        return []
