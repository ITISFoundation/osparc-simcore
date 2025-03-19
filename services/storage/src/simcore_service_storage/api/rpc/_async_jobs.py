# pylint: disable=unused-argument

import logging

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
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
)
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RPCRouter

from ...modules.celery import get_celery_client
from ...modules.celery.client import CeleryTaskQueueClient
from ...modules.celery.models import TaskError, TaskState

_logger = logging.getLogger(__name__)
router = RPCRouter()


async def _assert_job_exists(
    *,
    job_id: AsyncJobId,
    job_id_data: AsyncJobNameData,
    celery_client: CeleryTaskQueueClient,
) -> None:
    """Raises JobMissingError if job doesn't exist"""
    job_ids = await celery_client.get_task_uuids(
        task_context=job_id_data.model_dump(),
    )
    if not job_id in job_ids:
        raise JobMissingError(job_id=f"{job_id}")


@router.expose(reraise_if_error_type=(JobSchedulerError, JobMissingError))
async def abort(app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData):
    assert app  # nosec
    assert job_id_data  # nosec
    try:
        await _assert_job_exists(
            job_id=job_id, job_id_data=job_id_data, celery_client=get_celery_client(app)
        )
        await get_celery_client(app).abort_task(
            task_context=job_id_data.model_dump(),
            task_uuid=job_id,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc


@router.expose(reraise_if_error_type=(JobSchedulerError, JobMissingError))
async def get_status(
    app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData
) -> AsyncJobStatus:
    assert app  # nosec
    assert job_id_data  # nosec

    try:
        await _assert_job_exists(
            job_id=job_id, job_id_data=job_id_data, celery_client=get_celery_client(app)
        )
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
        JobMissingError,
    )
)
async def get_result(
    app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData
) -> AsyncJobResult:
    assert app  # nosec
    assert job_id  # nosec
    assert job_id_data  # nosec

    try:
        await _assert_job_exists(
            job_id=job_id, job_id_data=job_id_data, celery_client=get_celery_client(app)
        )
        status = await get_celery_client(app).get_task_status(
            task_context=job_id_data.model_dump(),
            task_uuid=job_id,
        )
        if not status.is_done:
            raise JobNotDoneError(job_id=job_id)
        result = await get_celery_client(app).get_task_result(
            task_context=job_id_data.model_dump(),
            task_uuid=job_id,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc

    if status.task_state == TaskState.ABORTED:
        raise JobAbortedError(job_id=job_id)
    if status.task_state == TaskState.ERROR:
        exc_type = ""
        exc_msg = ""
        with log_catch(logger=_logger, reraise=False):
            task_error = TaskError.model_validate_json(result)
            exc_type = task_error.exc_type
            exc_msg = task_error.exc_msg
        raise JobError(job_id=job_id, exc_type=exc_type, exc_msg=exc_msg)

    return AsyncJobResult(result=result)


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
