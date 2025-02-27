# pylint: disable=unused-argument
from datetime import datetime

from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobAbort,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobNameData,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    ResultError,
    StatusError,
)
from servicelib.rabbitmq import RPCRouter

from ...modules.celery.models import TaskStatus, TaskUUID
from ...modules.celery.utils import get_celery_client

router = RPCRouter()


@router.expose()
async def abort(
    app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData
) -> AsyncJobAbort:
    assert app  # nosec
    assert job_id_data  # nosec
    return AsyncJobAbort(result=True, job_id=job_id)


@router.expose(reraise_if_error_type=(StatusError,))
async def get_status(
    app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData
) -> AsyncJobStatus:
    assert app  # nosec
    assert job_id_data  # nosec

    task_status: TaskStatus = await get_celery_client(app).get_task_status(
        task_context=job_id_data.model_dump(),
        task_uuid=job_id,
    )
    return AsyncJobStatus(
        job_id=job_id,
        progress=task_status.progress_report,
        done=False,
        started=datetime.now(),  # TODO: retrieve that
        stopped=None,  # TODO: retrieve that
    )


@router.expose(reraise_if_error_type=(ResultError,))
async def get_result(
    app: FastAPI, job_id: AsyncJobId, job_id_data: AsyncJobNameData
) -> AsyncJobResult:
    assert app  # nosec
    assert job_id  # nosec
    assert job_id_data  # nosec

    result = await get_celery_client(app).get_result(
        task_context=job_id_data.model_dump(),
        task_uuid=job_id,
    )

    return AsyncJobResult(result=result, error=None)


@router.expose()
async def list_jobs(
    app: FastAPI, filter_: str, job_id_data: AsyncJobNameData  # TODO: implement filter
) -> list[AsyncJobGet]:
    assert app  # nosec

    task_uuids: set[TaskUUID] = await get_celery_client(app).get_task_uuids(
        task_context=job_id_data.model_dump(),
    )

    return [AsyncJobGet(job_id=task_uuid) for task_uuid in task_uuids]
