import logging
from datetime import UTC, datetime, timedelta
from typing import Final

from celery_library.errors import (
    TaskManagerError,
    TaskNotFoundError,
    TransferableCeleryError,
    decode_celery_transferable_error,
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
from pydantic import NonNegativeFloat
from servicelib.celery.models import (
    OwnerMetadata,
    TaskState,
    TaskStreamItem,
    TaskUUID,
)
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_catch

_logger = logging.getLogger(__name__)


_STREAM_STALL_THRESHOLD: Final[NonNegativeFloat] = timedelta(minutes=1).total_seconds()


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
            assert isinstance(_result, TransferableCeleryError)  # nosec
            exception = decode_celery_transferable_error(_result)
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


async def pull_task_stream_items(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    task_uuid: TaskUUID,
    limit: int = 50,
) -> tuple[list[TaskStreamItem], bool]:
    try:
        results, end, last_update = await task_manager.pull_task_stream_items(
            owner_metadata=owner_metadata,
            task_uuid=task_uuid,
            limit=limit,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=task_uuid) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    if not end and last_update:
        delta = datetime.now(UTC) - last_update
        if delta.total_seconds() > _STREAM_STALL_THRESHOLD:
            raise JobSchedulerError(exc=f"Task seems stalled since {delta.total_seconds()} seconds")

    return results, end


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

    return [AsyncJobGet(job_id=task.uuid, job_name=task.metadata.name) for task in tasks]
