# pylint: disable=unused-argument

import logging

from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
)
from servicelib.celery.models import OwnerMetadata, TaskState
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RPCRouter

from ..errors import (
    TaskManagerError,
    TaskNotFoundError,
    TransferableCeleryError,
    decode_celery_transferable_error,
)

_logger = logging.getLogger(__name__)
router = RPCRouter()


@router.expose(reraise_if_error_type=(JobSchedulerError, JobMissingError))
async def cancel(task_manager: TaskManager, job_id: AsyncJobId, owner_metadata: OwnerMetadata):
    assert task_manager  # nosec
    assert owner_metadata  # nosec
    try:
        await task_manager.cancel_task(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=job_id) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc


@router.expose(reraise_if_error_type=(JobSchedulerError, JobMissingError))
async def status(task_manager: TaskManager, job_id: AsyncJobId, owner_metadata: OwnerMetadata) -> AsyncJobStatus:
    assert task_manager  # nosec
    assert owner_metadata  # nosec

    try:
        task_status = await task_manager.get_task_status(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=job_id) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return AsyncJobStatus(
        job_id=job_id,
        progress=task_status.progress_report,
        done=task_status.is_done,
    )


@router.expose(
    reraise_if_error_type=(
        JobAbortedError,
        JobError,
        JobMissingError,
        JobNotDoneError,
        JobSchedulerError,
    )
)
async def result(task_manager: TaskManager, job_id: AsyncJobId, owner_metadata: OwnerMetadata) -> AsyncJobResult:
    assert task_manager  # nosec
    assert job_id  # nosec
    assert owner_metadata  # nosec

    try:
        _status = await task_manager.get_task_status(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
        if not _status.is_done:
            raise JobNotDoneError(job_id=job_id)
        _result = await task_manager.get_task_result(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=job_id) from exc
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

        # NOTE: cannot transfer original exception since this will not be able to be serialized
        # outside of storage
        raise JobError(job_id=job_id, exc_type=exc_type, exc_msg=exc_msg)

    return AsyncJobResult(result=_result)


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def list_jobs(task_manager: TaskManager, owner_metadata: OwnerMetadata) -> list[AsyncJobGet]:
    assert task_manager  # nosec
    try:
        tasks = await task_manager.list_tasks(
            owner_metadata=owner_metadata,
        )
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return [AsyncJobGet(job_id=task.uuid, job_name=task.metadata.name) for task in tasks]
