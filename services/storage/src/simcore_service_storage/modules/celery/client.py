import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.abortable import (  # type: ignore[import-untyped]
    AbortableAsyncResult,
)
from common_library.async_tools import make_async
from models_library.progress_bar import ProgressReport
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings

from .models import (
    TaskContext,
    TaskInfoStore,
    TaskMetadata,
    TaskState,
    TaskStatus,
    TaskUUID,
    build_task_id,
)

_logger = logging.getLogger(__name__)


_MIN_PROGRESS_VALUE = 0.0
_MAX_PROGRESS_VALUE = 1.0


@dataclass
class CeleryTaskClient:
    _celery_app: Celery
    _celery_settings: CelerySettings
    _task_store: TaskInfoStore

    async def send_task(
        self,
        task_metadata: TaskMetadata,
        *,
        task_context: TaskContext,
        **task_params,
    ) -> TaskUUID:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Submit {task_metadata.name=}: {task_context=} {task_params=}",
        ):
            task_uuid = uuid4()
            self._celery_app.send_task(
                task_metadata.name,
                task_id=build_task_id(task_context, task_uuid),
                kwargs=task_params,
                queue=task_metadata.queue.value,
            )

            expiry = (
                self._celery_settings.CELERY_EPHEMERAL_RESULT_EXPIRES
                if task_metadata.ephemeral
                else self._celery_settings.CELERY_RESULT_EXPIRES
            )
            await self._task_store.create(
                task_context, task_uuid, task_metadata, expiry=expiry
            )
            return task_uuid

    @make_async()
    def _abort_task(self, task_context: TaskContext, task_uuid: TaskUUID) -> None:
        AbortableAsyncResult(
            build_task_id(task_context, task_uuid), app=self._celery_app
        ).abort()

    async def abort_task(self, task_context: TaskContext, task_uuid: TaskUUID) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Abort task: {task_context=} {task_uuid=}",
        ):
            await self._abort_task(task_context, task_uuid)

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
                task_metadata = await self._task_store.get_metadata(
                    task_context, task_uuid
                )
                if task_metadata is not None and task_metadata.ephemeral:
                    await self._task_store.remove(task_context, task_uuid)
            return result

    async def _get_progress_report(
        self, task_context: TaskContext, task_uuid: TaskUUID, state: TaskState
    ) -> ProgressReport:
        if state in (TaskState.STARTED, TaskState.RETRY, TaskState.ABORTED):
            progress = await self._task_store.get_progress(task_context, task_uuid)
            if progress is not None:
                return progress
        if state in (
            TaskState.SUCCESS,
            TaskState.FAILURE,
        ):
            return ProgressReport(
                actual_value=_MAX_PROGRESS_VALUE, total=_MAX_PROGRESS_VALUE
            )

        # task is pending
        return ProgressReport(
            actual_value=_MIN_PROGRESS_VALUE, total=_MAX_PROGRESS_VALUE
        )

    @make_async()
    def _get_state(self, task_context: TaskContext, task_uuid: TaskUUID) -> TaskState:
        task_id = build_task_id(task_context, task_uuid)
        return TaskState(self._celery_app.AsyncResult(task_id).state)

    async def get_task_status(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> TaskStatus:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Getting task status: {task_context=} {task_uuid=}",
        ):
            task_state = await self._get_state(task_context, task_uuid)
            task_id = build_task_id(task_context, task_uuid)
            return TaskStatus(
                task_uuid=task_uuid,
                task_state=task_state,
                progress_report=await self._get_progress_report(task_id, task_state),
            )

    async def get_task_uuids(self, task_context: TaskContext) -> set[TaskUUID]:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Getting task uuids: {task_context=}",
        ):
            return await self._task_store.get_uuids(task_context)
