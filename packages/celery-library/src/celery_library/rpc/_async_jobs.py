# pylint: disable=unused-argument

import logging

from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobFilter,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobNotDoneError,
    JobSchedulerError,
)
from servicelib.celery.models import TaskState
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RPCRouter

from ..errors import (
    TransferrableCeleryError,
    decode_celery_transferrable_error,
)

_logger = logging.getLogger(__name__)
router = RPCRouter()


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def cancel(
    task_manager: TaskManager, job_id: AsyncJobId, job_filter: AsyncJobFilter
):
    assert task_manager  # nosec
    assert job_filter  # nosec
    try:
        await task_manager.cancel_task(
            task_filter=job_filter,
            task_uuid=job_id,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def status(
    task_manager: TaskManager, job_id: AsyncJobId, job_filter: AsyncJobFilter
) -> AsyncJobStatus:
    assert task_manager  # nosec
    assert job_filter  # nosec

    try:
        task_status = await task_manager.get_task_status(
            task_filter=job_filter,
            task_uuid=job_id,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return AsyncJobStatus(
        job_id=job_id,
        progress=task_status.progress_report,
        done=task_status.is_done,
    )


@router.expose(
    reraise_if_error_type=(
        JobError,
        JobNotDoneError,
        JobAbortedError,
        JobSchedulerError,
    )
)
async def result(
    task_manager: TaskManager, job_id: AsyncJobId, job_filter: AsyncJobFilter
) -> AsyncJobResult:
    assert task_manager  # nosec
    assert job_id  # nosec
    assert job_filter  # nosec

    try:
        _status = await task_manager.get_task_status(
            task_filter=job_filter,
            task_uuid=job_id,
        )
        if not _status.is_done:
            raise JobNotDoneError(job_id=job_id)
        _result = await task_manager.get_task_result(
            task_filter=job_filter,
            task_uuid=job_id,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    if _status.task_state == TaskState.ABORTED:
        raise JobAbortedError(job_id=job_id)
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

        # NOTE: cannot transfer original exception since this will not be able to be serialized
        # outside of storage
        raise JobError(job_id=job_id, exc_type=exc_type, exc_msg=exc_msg)

    return AsyncJobResult(result=_result)


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def list_jobs(
    task_manager: TaskManager, filter_: str, job_filter: AsyncJobFilter
) -> list[AsyncJobGet]:
    _ = filter_
    assert task_manager  # nosec
    try:
        tasks = await task_manager.list_tasks(
            task_filter=job_filter,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return [
        AsyncJobGet(job_id=task.uuid, job_name=task.metadata.name) for task in tasks
    ]
