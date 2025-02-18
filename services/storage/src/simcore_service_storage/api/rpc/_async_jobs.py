from datetime import datetime

from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobRpcAbort,
    AsyncJobRpcId,
    AsyncJobRpcResult,
    AsyncJobRpcStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    ResultError,
    StatusError,
)
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def abort(app: FastAPI, job_id: AsyncJobRpcId) -> AsyncJobRpcAbort:
    assert app  # nosec
    return AsyncJobRpcAbort(result=True, job_id=job_id)


@router.expose(reraise_if_error_type=(StatusError,))
async def get_status(app: FastAPI, job_id: AsyncJobRpcId) -> AsyncJobRpcStatus:
    assert app  # nosec
    return AsyncJobRpcStatus(
        job_id=job_id,
        task_progress=0.5,
        done=False,
        started=datetime.now(),
        stopped=None,
    )


@router.expose(reraise_if_error_type=(ResultError,))
async def get_result(app: FastAPI, job_id: AsyncJobRpcId) -> AsyncJobRpcResult:
    assert app  # nosec
    assert job_id  # nosec
    return AsyncJobRpcResult(result="Here's your result.", error=None)
