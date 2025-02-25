import logging
from typing import Any, Final
from uuid import uuid4

from celery import Celery
from celery.contrib.abortable import AbortableAsyncResult
from celery.result import AsyncResult
from fastapi import FastAPI
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

    def submit(
        self, task_name: str, *, task_id_parts: TaskIDParts, **task_params
    ) -> TaskID:
        task_id = _get_task_id(task_name, task_id_parts)
        _logger.debug("Submitting task %s: %s", task_name, task_id)
        task = self._celery_app.send_task(
            task_name, task_id=task_id, kwargs=task_params
        )
        assert isinstance(str, task.id)
        return task.id

    def get(self, task_id: TaskID) -> Any:
        return self._celery_app.tasks(task_id)

    def cancel(self, task_id: TaskID) -> None:
        _logger.info("Aborting task %s", task_id)
        AbortableAsyncResult(task_id).abort()

    def _get_async_result(self, task_id: TaskID) -> AsyncResult:
        return self._celery_app.AsyncResult(task_id)

    def get_result(self, task_id: TaskID) -> Any:
        return self._get_async_result(task_id).result

    def _get_progress_report(self, task_id: TaskID) -> ProgressReport | None:
        result = self._get_async_result(task_id).result
        if result:
            try:
                return ProgressReport.model_validate(result)
            except ValidationError:
                pass
        return None

    def get_status(self, task_id: TaskID) -> TaskStatus:
        return TaskStatus(
            task_id=task_id,
            task_state=self._get_async_result(task_id).state,
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
        if hasattr(redis, "keys"):
            if keys := redis.keys(search_key):
                return [f"{key}".lstrip(_CELERY_TASK_META_PREFIX) for key in keys]
        return []

    def list(self, task_name: str, *, task_id_parts: TaskIDParts) -> list[TaskID]:
        all_task_ids = self._get_completed_task_ids(task_name, task_id_parts)

        for task_type in ["active", "registered", "scheduled", "revoked"]:
            if task_ids := getattr(self._celery_app.control.inspect(), task_type)():
                all_task_ids.extend(task_ids)

        return all_task_ids


def get_client(fastapi: FastAPI) -> CeleryTaskQueueClient:
    celery = fastapi.state.celery_app
    assert isinstance(celery, Celery)

    client = celery.conf["client"]
    assert isinstance(client, CeleryTaskQueueClient)
    return client
