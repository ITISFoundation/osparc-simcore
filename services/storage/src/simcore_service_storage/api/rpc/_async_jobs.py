# pylint: disable=unused-argument
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobAbort,
    AsyncJobAccessData,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    ResultError,
    StatusError,
)
from models_library.progress_bar import ProgressReport
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def abort(
    app: FastAPI, job_id: AsyncJobId, access_data: AsyncJobAccessData | None
) -> AsyncJobAbort:
    assert app  # nosec
    return AsyncJobAbort(result=True, job_id=job_id)


@router.expose(reraise_if_error_type=(StatusError,))
async def get_status(
    app: FastAPI, job_id: AsyncJobId, access_data: AsyncJobAccessData | None
) -> AsyncJobStatus:
    assert app  # nosec
    progress_report = ProgressReport(actual_value=0.5, total=1.0, attempt=1)
    return AsyncJobStatus(
        job_id=job_id,
        progress=progress_report,
        done=False,
        started=datetime.now(),
        stopped=None,
    )


@router.expose(reraise_if_error_type=(ResultError,))
async def get_result(
    app: FastAPI, job_id: AsyncJobId, access_data: AsyncJobAccessData | None
) -> AsyncJobResult:
    assert app  # nosec
    assert job_id  # nosec
    return AsyncJobResult(result="Here's your result.", error=None)


@router.expose()
async def list_jobs(app: FastAPI, filter: str) -> list[AsyncJobGet]:
    assert app  # nosec
    return [AsyncJobGet(job_id=AsyncJobId(f"{uuid4()}"), job_name="myjob")]
