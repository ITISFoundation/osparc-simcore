from typing import Any, Final, TypeAlias
from uuid import uuid4

from celery import Celery
from celery.result import AsyncResult
from models_library.progress_bar import ProgressReport
from pydantic import ValidationError

from ..models import TaskID, TaskProgress

_PREFIX: Final = "AJ"

TaskIdComponents: TypeAlias = dict[str, Any]


def _get_task_id_components(task_id_components: TaskIdComponents) -> list[str]:
    return [f"{v}" for _, v in sorted(task_id_components.items())]


def _get_components_prefix(
    name: str, task_id_components: TaskIdComponents
) -> list[str]:
    return [_PREFIX, name, *_get_task_id_components(task_id_components)]


def _get_task_id_prefix(name: str, task_id_components: TaskIdComponents) -> TaskID:
    return "::".join(_get_components_prefix(name, task_id_components))


def _get_task_id(name: str, task_id_components: TaskIdComponents) -> TaskID:
    return "::".join([*_get_components_prefix(name, task_id_components), f"{uuid4()}"])


class CeleryClientInterface:
    def __init__(self, celery_app: Celery):
        self._celery_app = celery_app

    def submit(
        self, task_name: str, *, task_id_components: TaskIdComponents, **task_params
    ) -> TaskID:
        task_id = _get_task_id(task_name, task_id_components)
        task = self._celery_app.send_task(
            task_name, task_id=task_id, kwargs=task_params
        )
        return task.id

    def get(self, task_id: TaskID) -> Any:
        return self._celery_app.tasks(task_id)

    def cancel(self, task_id: TaskID) -> None:
        self._celery_app.control.revoke(task_id, terminate=True)

    def _get_async_result(self, task_id: TaskID) -> AsyncResult:
        return self._celery_app.AsyncResult(task_id)

    def get_result(self, task_id: TaskID) -> Any:
        # se manca il risultato o se va in FAILURE, ritorna error
        return self._get_async_result(task_id).result

    def _get_progress_report(self, task_id: TaskID) -> ProgressReport | None:
        result = self._get_async_result(task_id).result
        if result:
            try:
                return ProgressReport.model_validate(result)
            except ValidationError:
                return None

    def get_progress(self, task_id: TaskID) -> TaskProgress:
        return TaskProgress(
            task_id=task_id,
            task_state=self._get_async_result(task_id).state,
            progress_report=self._get_progress_report(task_id),
        )

    def list(
        self, task_name: str, *, task_id_components: TaskIdComponents
    ) -> list[TaskID]:
        prefix_to_search_in_redis = _get_task_id_prefix(task_name, task_id_components)
        return []
