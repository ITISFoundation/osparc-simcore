from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_rpc_data_export.async_jobs import AsyncJobRpcGet
from models_library.api_schemas_storage.data_export_async_jobs import (
    DataExportTaskStartInput,
)
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def start_data_export(
    app: FastAPI, paths: DataExportTaskStartInput
) -> AsyncJobRpcGet:
    assert app  # nosec
    return AsyncJobRpcGet(
        task_id=uuid4(),
        task_name=", ".join(str(p) for p in paths.paths),
    )
