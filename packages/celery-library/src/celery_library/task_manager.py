import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from celery import Celery  # type: ignore[import-untyped]
from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from common_library.async_tools import make_async
from models_library.progress_bar import ProgressReport
from servicelib.celery.models import (
    TASK_DONE_STATES,
    Task,
    TaskEvent,
    TaskEventID,
    TaskFilter,
    TaskID,
    TaskInfoStore,
    TaskMetadata,
    TaskState,
    TaskStatus,
    TaskUUID,
)
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings

from .errors import TaskNotFoundError, TaskSubmissionError, handle_celery_errors

_logger = logging.getLogger(__name__)


_MIN_PROGRESS_VALUE = 0.0
_MAX_PROGRESS_VALUE = 1.0


@dataclass(frozen=True)
class CeleryTaskManager:
    _celery_app: Celery
    _celery_settings: CelerySettings
    _task_info_store: TaskInfoStore

    @handle_celery_errors
    async def submit_task(
        self,
        task_metadata: TaskMetadata,
        *,
        task_filter: TaskFilter,
        **task_params,
    ) -> TaskUUID:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Submit {task_metadata.name=}: {task_filter=} {task_params=}",
        ):
            task_uuid = uuid4()
            task_id = task_filter.create_task_id(task_uuid=task_uuid)

            expiry = (
                self._celery_settings.CELERY_EPHEMERAL_RESULT_EXPIRES
                if task_metadata.ephemeral
                else self._celery_settings.CELERY_RESULT_EXPIRES
            )

            try:
                await self._task_info_store.create_task(
                    task_id, task_metadata, expiry=expiry
                )
                self._celery_app.send_task(
                    task_metadata.name,
                    task_id=task_id,
                    kwargs={"task_id": task_id} | task_params,
                    queue=task_metadata.queue.value,
                )
            except CeleryError as exc:
                try:
                    await self._task_info_store.remove_task(task_id)
                except CeleryError:
                    _logger.warning(
                        "Unable to cleanup task '%s' during error handling",
                        task_id,
                        exc_info=True,
                    )
                raise TaskSubmissionError(
                    task_name=task_metadata.name,
                    task_id=task_id,
                    task_params=task_params,
                ) from exc

            return task_uuid

    @handle_celery_errors
    async def cancel_task(self, task_filter: TaskFilter, task_uuid: TaskUUID) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"task cancellation: {task_filter=} {task_uuid=}",
        ):
            task_id = task_filter.create_task_id(task_uuid=task_uuid)
            if not await self.task_exists(task_id):
                raise TaskNotFoundError(task_id=task_id)

            await self._task_info_store.remove_task(task_id)
            await self._forget_task(task_id)

    async def task_exists(self, task_id: TaskID) -> bool:
        return await self._task_info_store.task_exists(task_id)

    @make_async()
    def _forget_task(self, task_id: TaskID) -> None:
        self._celery_app.AsyncResult(task_id).forget()

    @handle_celery_errors
    async def get_task_result(
        self, task_filter: TaskFilter, task_uuid: TaskUUID
    ) -> Any:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Get task result: {task_filter=} {task_uuid=}",
        ):
            task_id = task_filter.create_task_id(task_uuid=task_uuid)
            if not await self.task_exists(task_id):
                raise TaskNotFoundError(task_id=task_id)

            async_result = self._celery_app.AsyncResult(task_id)
            result = async_result.result
            if async_result.ready():
                task_metadata = await self._task_info_store.get_task_metadata(task_id)
                if task_metadata is not None and task_metadata.ephemeral:
                    await self._task_info_store.remove_task(task_id)
                    await self._forget_task(task_id)
            return result

    async def _get_task_progress_report(
        self, task_id: TaskID, task_state: TaskState
    ) -> ProgressReport:
        if task_state in (TaskState.STARTED, TaskState.RETRY):
            progress = await self._task_info_store.get_task_progress(task_id)
            if progress is not None:
                return progress

        if task_state in TASK_DONE_STATES:
            return ProgressReport(
                actual_value=_MAX_PROGRESS_VALUE, total=_MAX_PROGRESS_VALUE
            )

        # task is pending
        return ProgressReport(
            actual_value=_MIN_PROGRESS_VALUE, total=_MAX_PROGRESS_VALUE
        )

    @make_async()
    def _get_task_celery_state(self, task_id: TaskID) -> TaskState:
        return TaskState(self._celery_app.AsyncResult(task_id).state)

    @handle_celery_errors
    async def get_task_status(
        self, task_filter: TaskFilter, task_uuid: TaskUUID
    ) -> TaskStatus:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Getting task status: {task_filter=} {task_uuid=}",
        ):
            task_id = task_filter.create_task_id(task_uuid=task_uuid)
            if not await self.task_exists(task_id):
                raise TaskNotFoundError(task_id=task_id)

            task_state = await self._get_task_celery_state(task_id)
            return TaskStatus(
                task_uuid=task_uuid,
                task_state=task_state,
                progress_report=await self._get_task_progress_report(
                    task_id, task_state
                ),
            )

    @handle_celery_errors
    async def list_tasks(self, task_filter: TaskFilter) -> list[Task]:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Listing tasks: {task_filter=}",
        ):
            return await self._task_info_store.list_tasks(task_filter)

    @handle_celery_errors
    async def set_task_progress(self, task_id: TaskID, report: ProgressReport) -> None:
        await self._task_info_store.set_task_progress(
            task_id=task_id,
            report=report,
        )

    @handle_celery_errors
    async def publish_task_event(self, task_id: TaskID, event: TaskEvent) -> None:
        await self._task_info_store.publish_task_event(task_id, event)

    @handle_celery_errors
    async def consume_task_events(
        self,
        task_filter: TaskFilter,
        task_uuid: TaskUUID,
        last_id: str | None = None,
    ) -> AsyncIterator[tuple[TaskEventID, TaskEvent]]:
        task_id = task_filter.create_task_id(task_uuid=task_uuid)
        async for event in self._task_info_store.consume_task_events(
            task_id=task_id, last_id=last_id
        ):
            yield event


if TYPE_CHECKING:
    _: type[TaskManager] = CeleryTaskManager
