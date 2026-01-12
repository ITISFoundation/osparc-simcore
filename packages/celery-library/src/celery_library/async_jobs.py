# pylint: disable=unused-argument

import logging

from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_async_jobs.exceptions import (
    JobError,
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
)
from servicelib.celery.models import OwnerMetadata, TaskState
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_catch

from .errors import (
    TaskManagerError,
    TaskNotFoundError,
    TransferableCeleryError,
    decode_celery_transferable_error,
)

_logger = logging.getLogger(__name__)


async def cancel_job(
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
):
    try:
        await task_manager.cancel_task(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=job_id) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc


async def get_job_result(
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
) -> AsyncJobResult:
    assert task_manager  # nosec
    assert job_id  # nosec
    assert owner_metadata  # nosec

    try:
        task_status = await task_manager.get_task_status(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
        if not task_status.is_done:
            raise JobNotDoneError(job_id=job_id)
        task_result = await task_manager.get_task_result(
            owner_metadata=owner_metadata,
            task_uuid=job_id,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=job_id) from exc
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    if task_status.task_state == TaskState.FAILURE:
        # fallback exception to report
        exc_type = type(task_result).__name__
        exc_msg = f"{task_result}"

        # try to recover the original error
        exception = None
        with log_catch(_logger, reraise=False):
            assert isinstance(task_result, TransferableCeleryError)  # nosec
            exception = decode_celery_transferable_error(task_result)
            exc_type = type(exception).__name__
            exc_msg = f"{exception}"

        if exception is None:
            _logger.warning("Was not expecting '%s': '%s'", exc_type, exc_msg)

        # NOTE: cannot transfer original exception since this will not be able to be serialized
        # outside of storage
        raise JobError(job_id=job_id, exc_type=exc_type, exc_msg=exc_msg)

    return AsyncJobResult(result=task_result)


async def get_job_status(
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    job_id: AsyncJobId,
) -> AsyncJobStatus:
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


async def list_jobs(task_manager: TaskManager, owner_metadata: OwnerMetadata) -> list[AsyncJobGet]:
    assert task_manager  # nosec
    try:
        tasks = await task_manager.list_tasks(
            owner_metadata=owner_metadata,
        )
    except TaskManagerError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return [AsyncJobGet(job_id=task.uuid, job_name=task.metadata.name) for task in tasks]
