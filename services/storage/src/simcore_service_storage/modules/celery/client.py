import logging
from typing import Any, Final
from uuid import uuid4

from celery import Celery
from celery.contrib.abortable import AbortableAsyncResult
from common_library.async_tools import make_async
from models_library.progress_bar import ProgressReport
from pydantic import ValidationError

from .models import TaskID, TaskIDParts, TaskStatus

_logger = logging.getLogger(__name__)

_CELERY_TASK_META_PREFIX = "celery-task-meta-"
_PREFIX: Final[str] = "ct"  # short for celery task, not Catania
_CELERY_INSPECT_TASK_STATUSES = (
    "active",
    "registered",
    "scheduled",
    "revoked",
)


def _build_parts_prefix(name: str, task_id_parts: TaskIDParts) -> list[str]:
    return [_PREFIX, name, *[f"{task_id_parts[key]}" for key in sorted(task_id_parts)]]


def build_task_id_prefix(name: str, task_id_parts: TaskIDParts) -> TaskID:
    return "::".join(_build_parts_prefix(name, task_id_parts))


def build_task_id(name: str, task_id_parts: TaskIDParts) -> TaskID:
    return "::".join([*_build_parts_prefix(name, task_id_parts), f"{uuid4()}"])


class CeleryTaskQueueClient:
    def __init__(self, celery_app: Celery):
        self._celery_app = celery_app

    @make_async()
    def send_task(
        self, task_name: str, *, task_id_parts: TaskIDParts, **task_params
    ) -> TaskID:
        task_id = build_task_id(task_name, task_id_parts)
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
    ) -> set[TaskID]:
        search_key = (
            _CELERY_TASK_META_PREFIX
            + build_task_id_prefix(task_name, task_id_parts)
            + "*"
        )
        redis = self._celery_app.backend.client
        if hasattr(redis, "keys") and (keys := redis.keys(search_key)):
            return {f"{key}".removeprefix(_CELERY_TASK_META_PREFIX) for key in keys}
        return set()

    @make_async()
    def get_task_ids(
        self, task_name: str, *, task_id_parts: TaskIDParts
    ) -> set[TaskID]:
        all_task_ids = self._get_completed_task_ids(task_name, task_id_parts)

        for task_inspect_status in _CELERY_INSPECT_TASK_STATUSES:
            if task_ids := getattr(
                self._celery_app.control.inspect(), task_inspect_status
            )():
                all_task_ids.add(task_ids)

        return all_task_ids
