import logging
from collections.abc import AsyncIterator

from celery_library.errors import (
    TaskManagerError,
    TaskNotFoundError,
    TransferrableCeleryError,
    decode_celery_transferrable_error,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobError,
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
)
from servicelib.celery.models import (
    OwnerMetadata,
    TaskEvent,
    TaskEventID,
    TaskEventType,
    TaskState,
    TaskStatusValue,
    TaskUUID,
)
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_catch

_logger = logging.getLogger(__name__)


async def cancel_task(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
):
    try:
        await task_manager.cancel_task(
            owner_metadata=owner_metadata,
            task_uuid=task_uuid,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=task_uuid) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc


async def get_task_result(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
) -> AsyncJobResult:
    try:
        _status = await task_manager.get_task_status(
            owner_metadata=owner_metadata,
            task_uuid=task_uuid,
        )
        if not _status.is_done:
            raise JobNotDoneError(job_id=task_uuid)
        _result = await task_manager.get_task_result(
            owner_metadata=owner_metadata,
            task_uuid=task_uuid,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=task_uuid) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    if _status.task_state == TaskState.FAILURE:
        # fallback exception to report
        exc_type = type(_result).__name__
        exc_msg = f"{_result}"

        # try to recover the original error
        exception = None
        with log_catch(_logger, reraise=False):
            assert isinstance(_result, TransferrableCeleryError)  # nosec
            exception = decode_celery_transferrable_error(_result)
            exc_type = type(exception).__name__
            exc_msg = f"{exception}"

        if exception is None:
            _logger.warning("Was not expecting '%s': '%s'", exc_type, exc_msg)

        raise JobError(job_id=task_uuid, exc_type=exc_type, exc_msg=exc_msg)

    return AsyncJobResult(result=_result)


async def get_task_status(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
) -> AsyncJobStatus:
    try:
        task_status = await task_manager.get_task_status(
            owner_metadata=owner_metadata,
            task_uuid=task_uuid,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=task_uuid) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return AsyncJobStatus(
        job_id=task_uuid,
        progress=task_status.progress_report,
        done=task_status.is_done,
    )


async def list_tasks(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
) -> list[AsyncJobGet]:
    try:
        tasks = await task_manager.list_tasks(
            owner_metadata=owner_metadata,
        )
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return [
        AsyncJobGet(job_id=task.uuid, job_name=task.metadata.name) for task in tasks
    ]


async def consume_task_events(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
    last_event_id: TaskEventID | None = None,
) -> AsyncIterator[tuple[TaskEventID, TaskEvent]]:
    async for event_id, event in task_manager.consume_task_events(
        owner_metadata=owner_metadata,
        task_uuid=task_uuid,
        last_id=last_event_id,
    ):
        if event.type == TaskEventType.STATUS and event.data == TaskStatusValue.CREATED:
            continue

        yield event_id, event

        if event.type == TaskEventType.STATUS and event.is_done():
            break
