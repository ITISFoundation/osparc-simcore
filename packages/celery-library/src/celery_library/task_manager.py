import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from celery import Celery, group, signature  # type: ignore[import-untyped]
from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from celery.result import GroupResult  # type: ignore[import-untyped]
from common_library.async_tools import make_async
from models_library.progress_bar import ProgressReport
from pydantic import TypeAdapter
from servicelib.celery.models import (
    TASK_DONE_STATES,
    ExecutionMetadata,
    GroupStatus,
    GroupUUID,
    OwnerMetadata,
    Task,
    TaskKey,
    TaskParams,
    TaskState,
    TaskStatus,
    TaskStore,
    TaskStreamItem,
    TaskUUID,
)
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings

from .errors import GroupNotFoundError, TaskNotFoundError, TaskSubmissionError, handle_celery_errors

_logger = logging.getLogger(__name__)


_MIN_PROGRESS_VALUE = 0.0
_MAX_PROGRESS_VALUE = 1.0


@dataclass(frozen=True)
class CeleryTaskManager:
    _app: Celery
    _settings: CelerySettings
    _task_store: TaskStore

    def _get_task_expiry(self, execution_metadata: ExecutionMetadata) -> timedelta:
        return (
            self._settings.CELERY_EPHEMERAL_RESULT_EXPIRES
            if execution_metadata.ephemeral
            else self._settings.CELERY_RESULT_EXPIRES
        )

    async def _cleanup_task(self, task_key: TaskKey) -> None:
        try:
            await self._task_store.remove_task(task_key)
        except CeleryError:
            _logger.warning(
                "Unable to cleanup task '%s' during error handling",
                task_key,
                exc_info=True,
            )

    @staticmethod
    def _create_task_ids(owner_metadata: OwnerMetadata) -> tuple[TaskUUID, TaskKey]:
        """Generate task UUID and task key."""
        task_uuid = uuid4()
        task_key = owner_metadata.model_dump_key(task_or_group_uuid=task_uuid)
        return task_uuid, task_key

    @handle_celery_errors
    async def submit_group(
        self,
        executions: list[tuple[ExecutionMetadata, TaskParams]],
        *,
        owner_metadata: OwnerMetadata,
    ) -> tuple[GroupUUID, list[TaskUUID]]:
        """
        Submit a group of tasks in parallel.

        Returns: (group_id, list of TaskUUIDs in order)
        """
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Submit group: {owner_metadata=} items={len(executions)}",
        ):
            created: list[tuple[str, TaskUUID]] = []

            try:
                # Generate group UUID and key
                group_uuid = uuid4()
                group_key = owner_metadata.model_dump_key(task_or_group_uuid=group_uuid)

                # Prepare data for group creation
                signatures = []
                task_metadata_pairs: list[tuple[str, ExecutionMetadata]] = []
                expiries: list[timedelta] = []

                for execution_metadata, task_params in executions:
                    task_uuid, task_key = self._create_task_ids(owner_metadata)
                    expiry = self._get_task_expiry(execution_metadata)
                    expiries.append(expiry)

                    task_metadata_pairs.append((task_key, execution_metadata))

                    sig = signature(
                        execution_metadata.name,
                        kwargs={"task_key": task_key} | task_params,
                        queue=execution_metadata.queue,
                        task_id=task_key,
                        immutable=True,
                        app=self._app,
                    )
                    signatures.append(sig)
                    created.append((task_key, task_uuid))

                # Create all tasks in the group at once
                group_expiry = max(expiries) if expiries else self._settings.CELERY_RESULT_EXPIRES
                await self._task_store.create_group(group_key, task_metadata_pairs, expiry=group_expiry)

                group_result: GroupResult = group(signatures).apply_async()
                group_result.save()

            except CeleryError as exc:
                for task_key, _ in created:
                    await self._cleanup_task(task_key)

                raise TaskSubmissionError(
                    task_name="celery.group",
                    task_key=None,
                    task_params={"submitted": len(created)},
                ) from exc

            assert group_result.id is not None  # nosec
            return TypeAdapter(GroupUUID).validate_python(group_result.id), [
                TypeAdapter(TaskUUID).validate_python(task_uuid) for _, task_uuid in created
            ]

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
            task_uuid, task_key = self._create_task_ids(owner_metadata)
            expiry = self._get_task_expiry(execution_metadata)

            try:
                await self._task_store.create_task(task_key, execution_metadata, expiry=expiry)
                self._app.send_task(
                    execution_metadata.name,
                    task_id=task_key,
                    kwargs={"task_key": task_key} | task_params,
                    queue=execution_metadata.queue,
                )
            except CeleryError as exc:
                await self._cleanup_task(task_key)
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
            task_key = owner_metadata.model_dump_key(task_or_group_uuid=task_uuid)
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_uuid=task_uuid, owner_metadata=owner_metadata)

            await self._task_store.remove_task(task_key)
            await self._forget_task(task_key)

    async def task_exists(self, task_key: TaskKey) -> bool:
        return await self._task_store.task_or_group_exists(task_key)

    @make_async()
    def _forget_task(self, task_key: TaskKey) -> None:
        self._app.AsyncResult(task_key).forget()

    @handle_celery_errors
    async def get_task_result(self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID) -> Any:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Get task result: {owner_metadata=} {task_uuid=}",
        ):
            task_key = owner_metadata.model_dump_key(task_or_group_uuid=task_uuid)
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_uuid=task_uuid, owner_metadata=owner_metadata)

            async_result = self._app.AsyncResult(task_key)
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
        return TaskState(self._app.AsyncResult(task_key).state)

    @handle_celery_errors
    async def get_task_status(self, owner_metadata: OwnerMetadata, task_uuid: TaskUUID) -> TaskStatus:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Getting task status: {owner_metadata=} {task_uuid=}",
        ):
            task_key = owner_metadata.model_dump_key(task_or_group_uuid=task_uuid)
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_uuid=task_uuid, owner_metadata=owner_metadata)

            task_state = await self._get_task_celery_state(task_key)
            return TaskStatus(
                task_uuid=task_uuid,
                task_state=task_state,
                progress_report=await self._get_task_progress_report(task_key, task_state),
            )

    @make_async()
    def _restore_group_result(self, group_uuid: GroupUUID) -> GroupResult | None:
        """Restore a GroupResult from its ID."""
        try:
            return GroupResult.restore(str(group_uuid), app=self._app)
        except (KeyError, AttributeError):
            # Group not found or invalid
            return None

    @handle_celery_errors
    async def get_group_status(self, owner_metadata: OwnerMetadata, group_uuid: GroupUUID) -> GroupStatus:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"Getting group status: {owner_metadata=} {group_uuid=}",
        ):
            group_result = await self._restore_group_result(group_uuid)

            if group_result is None:
                raise GroupNotFoundError(group_uuid=group_uuid)

            # Get task UUIDs from the group result
            # AsyncResult objects have .id attribute containing the task key
            task_uuids = [
                OwnerMetadata.get_task_or_group_uuid(async_result.id) for async_result in (group_result.results or [])
            ]

            # Check group status
            completed_count = group_result.completed_count()
            is_done = group_result.ready()
            is_successful = group_result.successful() if is_done else False

            return GroupStatus(
                group_uuid=group_uuid,
                task_uuids=task_uuids,
                completed_count=completed_count,
                total_count=len(task_uuids),
                is_done=is_done,
                is_successful=is_successful,
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
            task_key = owner_metadata.model_dump_key(task_or_group_uuid=task_uuid)
            if not await self.task_exists(task_key):
                raise TaskNotFoundError(task_key=task_key)

            return await self._task_store.pull_task_stream_items(task_key, limit)


if TYPE_CHECKING:
    _: type[TaskManager] = CeleryTaskManager
