# pylint: disable=unused-argument

import logging

from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from celery_library.errors import (
    TransferrableCeleryError,
    decode_celery_transferrable_error,
)
from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobNameData,
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
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RPCRouter

from ...modules.celery import get_task_manager_from_app

_logger = logging.getLogger(__name__)
router = RPCRouter()


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def cancel(app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData):
    assert app  # nosec
    assert job_id_data  # nosec
    try:
        await get_task_manager_from_app(app).cancel_task(
            task_context=job_id_data.model_dump(),
            task_uuid=job_id,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def status(
    app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData
) -> AsyncJobStatus:
    assert app  # nosec
    assert job_id_data  # nosec

    try:
        task_status = await get_task_manager_from_app(app).get_task_status(
            task_context=job_id_data.model_dump(),
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
    app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData
) -> AsyncJobResult:
    assert app  # nosec
    assert job_id  # nosec
    assert job_id_data  # nosec

    try:
        _status = await get_task_manager_from_app(app).get_task_status(
            task_context=job_id_data.model_dump(),
            task_uuid=job_id,
        )
        if not _status.is_done:
            raise JobNotDoneError(job_id=job_id)
        _result = await get_task_manager_from_app(app).get_task_result(
            task_context=job_id_data.model_dump(),
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
            _logger.warning("Was not expecting '%s': '%s'", exc_type, exc_msg)  # type: ignore[unreachable]

        # NOTE: cannot transfer original exception since this will not be able to be serialized
        # outside of storage
        raise JobError(job_id=job_id, exc_type=exc_type, exc_msg=exc_msg)

    return AsyncJobResult(result=_result)


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def list_jobs(
    app: FastAPI, filter_: str, job_id_data: AsyncJobNameData
) -> list[AsyncJobGet]:
    _ = filter_
    assert app  # nosec
    try:
        tasks = await get_task_manager_from_app(app).list_tasks(
            task_context=job_id_data.model_dump(),
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return [
        AsyncJobGet(job_id=task.uuid, job_name=task.metadata.name) for task in tasks
    ]
