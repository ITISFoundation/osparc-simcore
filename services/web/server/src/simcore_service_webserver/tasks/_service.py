import logging

from celery_library.errors import (
    InternalError,
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
from servicelib.celery.models import TaskFilter, TaskState, TaskUUID
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_catch

_logger = logging.getLogger(__name__)


async def cancel_task(
    task_manager: TaskManager,
    task_filter: TaskFilter,
    task_uuid: TaskUUID,
):
    try:
        await task_manager.cancel_task(
            task_filter=task_filter,
            task_uuid=task_uuid,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=task_uuid) from exc
    except InternalError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc


async def get_task_result(
    task_manager: TaskManager,
    task_filter: TaskFilter,
    task_uuid: TaskUUID,
) -> AsyncJobResult:
    try:
        _status = await task_manager.get_task_status(
            task_filter=task_filter,
            task_uuid=task_uuid,
        )
        if not _status.is_done:
            raise JobNotDoneError(job_id=task_uuid)
        _result = await task_manager.get_task_result(
            task_filter=task_filter,
            task_uuid=task_uuid,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=task_uuid) from exc
    except InternalError as exc:
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
    task_filter: TaskFilter,
    task_uuid: TaskUUID,
) -> AsyncJobStatus:
    try:
        task_status = await task_manager.get_task_status(
            task_filter=task_filter,
            task_uuid=task_uuid,
        )
    except TaskNotFoundError as exc:
        raise JobMissingError(job_id=task_uuid) from exc
    except InternalError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return AsyncJobStatus(
        job_id=task_uuid,
        progress=task_status.progress_report,
        done=task_status.is_done,
    )


async def list_tasks(
    task_manager: TaskManager,
    task_filter: TaskFilter,
) -> list[AsyncJobGet]:
    try:
        tasks = await task_manager.list_tasks(
            task_filter=task_filter,
        )
    except InternalError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return [
        AsyncJobGet(job_id=task.uuid, job_name=task.metadata.name) for task in tasks
    ]
