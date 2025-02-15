from datetime import datetime

from fastapi import FastAPI
from models_library.api_schemas_rpc_data_export.async_jobs import (
    AsyncJobRpcId,
    AsyncJobRpcResult,
    AsyncJobRpcStatus,
)
from models_library.api_schemas_storage.data_export_tasks import (
    DataExportTaskAbortOutput,
)
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def abort(app: FastAPI, task_id: AsyncJobRpcId) -> DataExportTaskAbortOutput:
    assert app  # nosec
    return DataExportTaskAbortOutput(result=True, task_id=task_id)


@router.expose()
async def get_status(app: FastAPI, task_id: AsyncJobRpcId) -> AsyncJobRpcStatus:
    assert app  # nosec
    return AsyncJobRpcStatus(
        task_id=task_id,
        task_progress=0.5,
        done=False,
        started=datetime.now(),
        stopped=None,
    )


@router.expose()
async def get_result(app: FastAPI, task_id: AsyncJobRpcId) -> AsyncJobRpcResult:
    assert app  # nosec
    assert task_id  # nosec
    return AsyncJobRpcResult(result="Here's your result.", error=None)
