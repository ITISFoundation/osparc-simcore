# pylint: disable=unused-argument

import base64
import logging
import pickle

from celery.exceptions import CeleryError  # type: ignore[import-untyped]
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
from servicelib.rabbitmq import RPCRouter

from ...modules.celery import get_celery_client
from ...modules.celery.models import TaskState

_logger = logging.getLogger(__name__)
router = RPCRouter()


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def cancel(app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData):
    assert app  # nosec
    assert job_id_data  # nosec
    try:
        await get_celery_client(app).abort_task(
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
        task_status = await get_celery_client(app).get_task_status(
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
        _status = await get_celery_client(app).get_task_status(
            task_context=job_id_data.model_dump(),
            task_uuid=job_id,
        )
        if not _status.is_done:
            raise JobNotDoneError(job_id=job_id)
        _result = await get_celery_client(app).get_task_result(
            task_context=job_id_data.model_dump(),
            task_uuid=job_id,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    if _status.task_state == TaskState.ABORTED:
        raise JobAbortedError(job_id=job_id)
    if _status.task_state == TaskState.ERROR:
        # NOTE: recover original error from wrapped error
        exception = pickle.loads(base64.b64decode(_result.args[0]))
        exc_type = type(exception).__name__
        exc_msg = f"{exception}"
        raise JobError(job_id=job_id, exc_type=exc_type, exc_msg=exc_msg, exc=exception)

    return AsyncJobResult(result=_result)


@router.expose(reraise_if_error_type=(JobSchedulerError,))
async def list_jobs(
    app: FastAPI, filter_: str, job_id_data: AsyncJobNameData
) -> list[AsyncJobGet]:
    assert app  # nosec
    try:
        task_uuids = await get_celery_client(app).get_task_uuids(
            task_context=job_id_data.model_dump(),
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    return [AsyncJobGet(job_id=task_uuid) for task_uuid in task_uuids]
