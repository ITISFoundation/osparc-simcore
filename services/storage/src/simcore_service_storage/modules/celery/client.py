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
from settings_library.celery import CelerySettings

from .models import (
    TaskContext,
    TaskID,
    TaskInfoStore,
    TaskMetadata,
    TaskState,
    TaskStatus,
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
    _celery_settings: CelerySettings
    _task_store: TaskInfoStore

    async def send_task(
        self,
        task_name: str,
        *,
        task_context: TaskContext,
        task_metadata: TaskMetadata | None = None,
        **task_params,
    ) -> TaskUUID:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Submit {task_name=}: {task_context=} {task_params=}",
        ):
            task_uuid = uuid4()
            task_id = build_task_id(task_context, task_uuid)
            task_metadata = task_metadata or TaskMetadata()
            self._celery_app.send_task(
                task_name,
                task_id=task_id,
                kwargs=task_params,
                queue=task_metadata.queue.value,
            )

            expiry = (
                self._celery_settings.CELERY_EPHEMERAL_RESULT_EXPIRES
                if task_metadata.ephemeral
                else self._celery_settings.CELERY_RESULT_EXPIRES
            )
            await self._task_store.set_metadata(task_id, task_metadata, expiry=expiry)
            return task_uuid

    @make_async()
    def _abort_task(self, task_id: TaskID) -> None:
        AbortableAsyncResult(task_id, app=self._celery_app).abort()

    async def abort_task(self, task_context: TaskContext, task_uuid: TaskUUID) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Abort task: {task_context=} {task_uuid=}",
        ):
            task_id = build_task_id(task_context, task_uuid)
            await self._abort_task(task_id)

    @make_async()
    def _get_result(self, task_context: TaskContext, task_uuid: TaskUUID) -> Any:
        task_id = build_task_id(task_context, task_uuid)
        return self._celery_app.AsyncResult(task_id).result

    async def get_task_result(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> Any:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Get task result: {task_context=} {task_uuid=}",
        ):
            task_id = build_task_id(task_context, task_uuid)
            async_result = self._celery_app.AsyncResult(task_id)
            result = async_result.result
            if async_result.ready():
                task_metadata = await self._task_store.get_metadata(task_id)
                if task_metadata is not None and task_metadata.ephemeral:
                    await self._task_store.remove(task_id)
            return result

    @staticmethod
    async def _get_progress_report(state, result) -> ProgressReport:
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

    @make_async()
    def _get_state(self, task_context: TaskContext, task_uuid: TaskUUID) -> TaskState:
        task_id = build_task_id(task_context, task_uuid)
        return _CELERY_STATES_MAPPING[self._celery_app.AsyncResult(task_id).state]

    async def get_task_status(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> TaskStatus:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Getting task status: {task_context=} {task_uuid=}",
        ):
            task_state = await self._get_state(task_context, task_uuid)
            result = await self._get_result(task_context, task_uuid)
            return TaskStatus(
                task_uuid=task_uuid,
                task_state=task_state,
                progress_report=await self._get_progress_report(task_state, result),
            )

    async def get_task_uuids(self, task_context: TaskContext) -> set[TaskUUID]:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Getting task uuids: {task_context=}",
        ):
            return await self._task_store.get_uuids(task_context)
