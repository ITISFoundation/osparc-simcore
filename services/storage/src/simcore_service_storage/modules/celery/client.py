import contextlib
import logging
from dataclasses import dataclass
from typing import Any, Final
from uuid import uuid4

from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.abortable import (  # type: ignore[import-untyped]
    AbortableAsyncResult,
)
from common_library.async_tools import make_async
from models_library.progress_bar import ProgressReport
from pydantic import ValidationError
from servicelib.logging_utils import log_context

from .models import (
    TaskContext,
    TaskData,
    TaskState,
    TaskStatus,
    TaskStore,
    TaskUUID,
    build_task_id,
)

_logger = logging.getLogger(__name__)

_CELERY_STATES_MAPPING: Final[dict[str, TaskState]] = {
    "PENDING": TaskState.PENDING,
    "STARTED": TaskState.PENDING,
    "RETRY": TaskState.PENDING,
    "RUNNING": TaskState.RUNNING,
    "SUCCESS": TaskState.SUCCESS,
    "ABORTED": TaskState.ABORTED,
    "FAILURE": TaskState.ERROR,
    "ERROR": TaskState.ERROR,
}

_MIN_PROGRESS_VALUE = 0.0
_MAX_PROGRESS_VALUE = 1.0


@dataclass
class CeleryTaskQueueClient:
    _celery_app: Celery
    _task_store: TaskStore

    async def send_task(
        self, task_name: str, *, task_context: TaskContext, **task_params
    ) -> TaskUUID:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Submit {task_name=}: {task_context=} {task_params=}",
        ):
            task_uuid = uuid4()
            task_id = build_task_id(task_context, task_uuid)
            self._celery_app.send_task(task_name, task_id=task_id, kwargs=task_params)
            await self._task_store.set_task(
                task_id, TaskData(status=TaskState.PENDING.name)
            )
            return task_uuid

    @staticmethod
    @make_async()
    def abort_task(task_context: TaskContext, task_uuid: TaskUUID) -> None:
        task_id = build_task_id(task_context, task_uuid)
        _logger.info("Aborting task %s", task_id)
        AbortableAsyncResult(task_id).abort()

    @make_async()
    def get_task_result(self, task_context: TaskContext, task_uuid: TaskUUID) -> Any:
        task_id = build_task_id(task_context, task_uuid)
        return self._celery_app.AsyncResult(task_id).result

    def _get_progress_report(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> ProgressReport:
        task_id = build_task_id(task_context, task_uuid)
        result = self._celery_app.AsyncResult(task_id).result
        state = self._get_state(task_context, task_uuid)
        if result and state == TaskState.RUNNING:
            with contextlib.suppress(ValidationError):
                # avoids exception if result is not a ProgressReport (or overwritten by a Celery's state update)
                return ProgressReport.model_validate(result)
        if state in (
            TaskState.ABORTED,
            TaskState.ERROR,
            TaskState.SUCCESS,
        ):
            return ProgressReport(
                actual_value=_MAX_PROGRESS_VALUE, total=_MAX_PROGRESS_VALUE
            )
        return ProgressReport(
            actual_value=_MIN_PROGRESS_VALUE, total=_MAX_PROGRESS_VALUE
        )

    def _get_state(self, task_context: TaskContext, task_uuid: TaskUUID) -> TaskState:
        task_id = build_task_id(task_context, task_uuid)
        return _CELERY_STATES_MAPPING[self._celery_app.AsyncResult(task_id).state]

    @make_async()
    def get_task_status(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> TaskStatus:
        return TaskStatus(
            task_uuid=task_uuid,
            task_state=self._get_state(task_context, task_uuid),
            progress_report=self._get_progress_report(task_context, task_uuid),
        )

    async def get_task_uuids(self, task_context: TaskContext) -> set[TaskUUID]:
        return await self._task_store.get_task_uuids(task_context)
