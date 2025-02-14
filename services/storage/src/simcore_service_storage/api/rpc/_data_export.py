from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_rpc_data_export.tasks import TaskRpcGet
from models_library.api_schemas_storage.data_export_tasks import (
    DataExportTaskStartInput,
)
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def start_data_export(
    app: FastAPI, paths: DataExportTaskStartInput
) -> TaskRpcGet:
    assert app  # nosec
    return TaskRpcGet(
        task_id=uuid4(),
        task_name=", ".join(str(p) for p in paths.paths),
    )
