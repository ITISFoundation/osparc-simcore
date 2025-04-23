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
    Task,
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


_MIN_PROGRESS_VALUE = 0.0
_MAX_PROGRESS_VALUE = 1.0


@dataclass
class CeleryTaskClient:
    _celery_app: Celery
    _celery_settings: CelerySettings
    _task_info_store: TaskInfoStore

    async def submit_task(
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
            task_id = build_task_id(task_context, task_uuid)
            self._celery_app.send_task(
                task_metadata.name,
                task_id=task_id,
                kwargs=task_params,
                queue=task_metadata.queue.value,
            )

            expiry = (
                self._celery_settings.CELERY_EPHEMERAL_RESULT_EXPIRES
                if task_metadata.ephemeral
                else self._celery_settings.CELERY_RESULT_EXPIRES
            )
            await self._task_info_store.create_task(
                task_id, task_metadata, expiry=expiry
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

    @make_async()
    def _forget_task(self, task_id: TaskID) -> None:
        AbortableAsyncResult(task_id, app=self._celery_app).forget()

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
                task_metadata = await self._task_info_store.get_task_metadata(task_id)
                if task_metadata is not None and task_metadata.ephemeral:
                    await self._task_info_store.remove_task(task_id)
                    await self._forget_task(task_id)
            return result

    async def _get_task_progress_report(
        self, task_context: TaskContext, task_uuid: TaskUUID, task_state: TaskState
    ) -> ProgressReport:
        if task_state in (TaskState.STARTED, TaskState.RETRY, TaskState.ABORTED):
            task_id = build_task_id(task_context, task_uuid)
            progress = await self._task_info_store.get_task_progress(task_id)
            if progress is not None:
                return progress
        if task_state in (
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
    def _get_task_celery_state(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> TaskState:
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
            task_state = await self._get_task_celery_state(task_context, task_uuid)
            return TaskStatus(
                task_uuid=task_uuid,
                task_state=task_state,
                progress_report=await self._get_task_progress_report(
                    task_context, task_uuid, task_state
                ),
            )

    async def list_tasks(self, task_context: TaskContext) -> list[Task]:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Listing tasks: {task_context=}",
        ):
            return await self._task_info_store.list_tasks(task_context)
