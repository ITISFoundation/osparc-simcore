from datetime import datetime

from fastapi import FastAPI
from models_library.api_schemas_rpc_data_export.async_jobs import (
    AsyncJobRpcId,
    AsyncJobRpcResult,
    AsyncJobRpcStatus,
)
from models_library.api_schemas_storage.data_export_async_jobs import (
    DataExportTaskAbortOutput,
)
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def abort(app: FastAPI, job_id: AsyncJobRpcId) -> DataExportTaskAbortOutput:
    assert app  # nosec
    return DataExportTaskAbortOutput(result=True, task_id=job_id)


@router.expose()
async def get_status(app: FastAPI, job_id: AsyncJobRpcId) -> AsyncJobRpcStatus:
    assert app  # nosec
    return AsyncJobRpcStatus(
        job_id=job_id,
        task_progress=0.5,
        done=False,
        started=datetime.now(),
        stopped=None,
    )


@router.expose()
async def get_result(app: FastAPI, job_id: AsyncJobRpcId) -> AsyncJobRpcResult:
    assert app  # nosec
    assert job_id  # nosec
    return AsyncJobRpcResult(result="Here's your result.", error=None)
