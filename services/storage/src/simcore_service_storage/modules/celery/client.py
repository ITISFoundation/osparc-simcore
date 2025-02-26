import logging
from typing import Any, Final
from uuid import uuid4

from celery import Celery
from celery.contrib.abortable import AbortableAsyncResult
from common_library.async_tools import make_async
from models_library.progress_bar import ProgressReport
from pydantic import ValidationError

from .models import TaskID, TaskIDParts, TaskStatus

_PREFIX: Final = "ct"

_logger = logging.getLogger(__name__)


def _get_task_id_components(task_id_parts: TaskIDParts) -> list[str]:
    return [f"{v}" for _, v in sorted(task_id_parts.items())]


def _get_components_prefix(name: str, task_id_parts: TaskIDParts) -> list[str]:
    return [_PREFIX, name, *_get_task_id_components(task_id_parts)]


def _get_task_id_prefix(name: str, task_id_parts: TaskIDParts) -> TaskID:
    return "::".join(_get_components_prefix(name, task_id_parts))


def _get_task_id(name: str, task_id_parts: TaskIDParts) -> TaskID:
    return "::".join([*_get_components_prefix(name, task_id_parts), f"{uuid4()}"])


_CELERY_TASK_META_PREFIX = "celery-task-meta-"


class CeleryTaskQueueClient:
    def __init__(self, celery_app: Celery):
        self._celery_app = celery_app

    @make_async()
    def send_task(
        self, task_name: str, *, task_id_parts: TaskIDParts, **task_params
    ) -> TaskID:
        task_id = _get_task_id(task_name, task_id_parts)
        _logger.debug("Submitting task %s: %s", task_name, task_id)
        task = self._celery_app.send_task(
            task_name, task_id=task_id, kwargs=task_params
        )
        return task.id

    @make_async()
    def get_task(self, task_id: TaskID) -> Any:
        return self._celery_app.tasks(task_id)

    @make_async()
    def abort_task(self, task_id: TaskID) -> None:  # pylint: disable=R6301
        _logger.info("Aborting task %s", task_id)
        AbortableAsyncResult(task_id).abort()

    @make_async()
    def get_result(self, task_id: TaskID) -> Any:
        return self._celery_app.AsyncResult(task_id).result

    def _get_progress_report(self, task_id: TaskID) -> ProgressReport | None:
        result = self._celery_app.AsyncResult(task_id).result
        if result:
            try:
                return ProgressReport.model_validate(result)
            except ValidationError:
                pass
        return None

    @make_async()
    def get_task_status(self, task_id: TaskID) -> TaskStatus:
        return TaskStatus(
            task_id=task_id,
            task_state=self._celery_app.AsyncResult(task_id).state,
            progress_report=self._get_progress_report(task_id),
        )

    def _get_completed_task_ids(
        self, task_name: str, task_id_parts: TaskIDParts
    ) -> list[TaskID]:
        search_key = (
            _CELERY_TASK_META_PREFIX
            + _get_task_id_prefix(task_name, task_id_parts)
            + "*"
        )
        redis = self._celery_app.backend.client
        if hasattr(redis, "keys") and (keys := redis.keys(search_key)):
            return [f"{key}".lstrip(_CELERY_TASK_META_PREFIX) for key in keys]
        return []

    @make_async()
    def list_tasks(self, task_name: str, *, task_id_parts: TaskIDParts) -> Any:
        all_task_ids = self._get_completed_task_ids(task_name, task_id_parts)

        for task_type in ["active", "registered", "scheduled", "revoked"]:
            if task_ids := getattr(self._celery_app.control.inspect(), task_type)():
                all_task_ids.extend(task_ids)

        return all_task_ids
