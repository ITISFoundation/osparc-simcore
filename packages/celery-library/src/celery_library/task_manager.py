import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from celery import Celery  # type: ignore[import-untyped]
from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from common_library.async_tools import make_async
from models_library.progress_bar import ProgressReport
from servicelib.celery.models import (
    TASK_DONE_STATES,
    ExecutionMetadata,
    OwnerMetadata,
    Task,
    TaskKey,
    TaskState,
    TaskStatus,
    TaskStore,
    TaskStreamItem,
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
    _task_store: TaskStore

    @handle_celery_errors
    async def submit_task(
        self,
        execution_metadata: ExecutionMetadata,
        *,
        owner_metadata: OwnerMetadata,
        **task_params,
    ) -> TaskUUID:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Submit {execution_metadata.name=}: {owner_metadata=} {task_params=}",
        ):
            task_uuid = uuid4()
            task_key = owner_metadata.model_dump_task_key(task_uuid=task_uuid)

            expiry = (
                self._celery_settings.CELERY_EPHEMERAL_RESULT_EXPIRES
                if execution_metadata.ephemeral
                else self._celery_settings.CELERY_RESULT_EXPIRES
            )

            try:
                await self._task_store.create_task(task_key, execution_metadata, expiry=expiry)
                self._celery_app.send_task(
                    execution_metadata.name,
                    task_id=task_key,
                    kwargs={"task_key": task_key} | task_params,
                    queue=execution_metadata.queue,
                )
            except CeleryError as exc:
                try:
                    await self._task_store.remove_task(task_key)
                except CeleryError:
                    _logger.warning(
                        "Unable to cleanup task '%s' during error handling",
                        task_key,
                        exc_info=True,
                    )
                raise TaskSubmissionError(
                    task_name=execution_metadata.name,
                    task_key=task_key,
                    task_params=task_params,
                ) from exc

            return task_uuid

    @handle_celery_errors
    async def cancel_task(self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"task cancellation: {owner_metadata=} {task_uuid=}",
        ):
            task_key = owner_metadata.model_dump_task_key(task_uuid=task_uuid)
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_uuid=task_uuid, owner_metadata=owner_metadata)

            await self._task_store.remove_task(task_key)
            await self._forget_task(task_key)

    async def task_exists(self, task_key: TaskKey) -> bool:
        return await self._task_store.task_exists(task_key)

    @make_async()
    def _forget_task(self, task_key: TaskKey) -> None:
        self._celery_app.AsyncResult(task_key).forget()

    @handle_celery_errors
    async def get_task_result(self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID) -> Any:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Get task result: {owner_metadata=} {task_uuid=}",
        ):
            task_key = owner_metadata.model_dump_task_key(task_uuid=task_uuid)
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_uuid=task_uuid, owner_metadata=owner_metadata)

            async_result = self._celery_app.AsyncResult(task_key)
            result = async_result.result
            if async_result.ready():
                task_metadata = await self._task_store.get_task_metadata(task_key)
                if task_metadata is not None and task_metadata.ephemeral:
                    await self._task_store.remove_task(task_key)
                    await self._forget_task(task_key)
            return result

    async def _get_task_progress_report(self, task_key: TaskKey, task_state: TaskState) -> ProgressReport:
        if task_state in {TaskState.STARTED, TaskState.RETRY}:
            progress = await self._task_store.get_task_progress(task_key)
            if progress is not None:
                return progress

        if task_state in TASK_DONE_STATES:
            return ProgressReport(actual_value=_MAX_PROGRESS_VALUE, total=_MAX_PROGRESS_VALUE)

        # task is pending
        return ProgressReport(actual_value=_MIN_PROGRESS_VALUE, total=_MAX_PROGRESS_VALUE)

    @make_async()
    def _get_task_celery_state(self, task_key: TaskKey) -> TaskState:
        return TaskState(self._celery_app.AsyncResult(task_key).state)

    @handle_celery_errors
    async def get_task_status(self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID) -> TaskStatus:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Getting task status: {owner_metadata=} {task_uuid=}",
        ):
            task_key = owner_metadata.model_dump_task_key(task_uuid=task_uuid)
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_uuid=task_uuid, owner_metadata=owner_metadata)

            task_state = await self._get_task_celery_state(task_key)
            return TaskStatus(
                task_uuid=task_uuid,
                task_state=task_state,
                progress_report=await self._get_task_progress_report(task_key, task_state),
            )

    @handle_celery_errors
    async def list_tasks(self, owner_metadata: OwnerMetadata) -> list[Task]:
        with log_context(_logger, logging.DEBUG, "Listing tasks: owner_metadata=%s", owner_metadata):
            return await self._task_store.list_tasks(owner_metadata)

    @handle_celery_errors
    async def set_task_progress(self, task_key: TaskKey, report: ProgressReport) -> None:
        await self._task_store.set_task_progress(
            task_key=task_key,
            report=report,
        )

    @handle_celery_errors
    async def set_task_stream_done(self, task_key: TaskKey) -> None:
        with log_context(_logger, logging.DEBUG, "Set task stream done: task_key= %s", task_key):
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_key=task_key)

            await self._task_store.set_task_stream_done(task_key)

    @handle_celery_errors
    async def set_task_stream_last_update(self, task_key: TaskKey) -> None:
        with log_context(_logger, logging.DEBUG, "Set task stream last update: task_key=%s", task_key):
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_key=task_key)

            await self._task_store.set_task_stream_last_update(task_key)

    @handle_celery_errors
    async def push_task_stream_items(self, task_key: TaskKey, *items: TaskStreamItem) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            "Push task stream items: task_key=%s items=%s",
            task_key,
            items,
        ):
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_key=task_key)

            await self._task_store.push_task_stream_items(task_key, *items)

    @handle_celery_errors
    async def pull_task_stream_items(
        self,
        owner_metadata: OwnerMetadata,
        task_uuid: TaskUUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[TaskStreamItem], bool, datetime | None]:
        with log_context(
            _logger,
            logging.DEBUG,
            "Pull task results: owner_metadata=%s task_uuid=%s offset=%s limit=%s",
            owner_metadata,
            task_uuid,
            offset,
            limit,
        ):
            task_key = owner_metadata.model_dump_task_key(task_uuid=task_uuid)
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_key=task_key)

            return await self._task_store.pull_task_stream_items(task_key, limit)


if TYPE_CHECKING:
    _: type[TaskManager] = CeleryTaskManager
