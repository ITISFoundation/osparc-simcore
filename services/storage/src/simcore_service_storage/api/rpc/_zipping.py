from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_rpc_long_running_tasks.tasks import (
    TaskRpcGet,
    TaskRpcId,
    TaskRpcResult,
    TaskRpcStatus,
)
from models_library.api_schemas_storage.zipping_tasks import (
    ZipTaskAbortOutput,
    ZipTaskStartInput,
)
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def start_zipping(app: FastAPI, paths: ZipTaskStartInput) -> TaskRpcGet:
    assert app  # nosec
    return TaskRpcGet(
        task_id=uuid4(),
        task_name=", ".join(str(p) for p in paths.paths),
    )


@router.expose()
async def abort_zipping(app: FastAPI, task_id: TaskRpcId) -> ZipTaskAbortOutput:
    assert app  # nosec
    return ZipTaskAbortOutput(result=True, task_id=task_id)


@router.expose()
async def get_zipping_status(app: FastAPI, task_id: TaskRpcId) -> TaskRpcStatus:
    assert app  # nosec
    return TaskRpcStatus(
        task_id=task_id,
        task_progress=0.5,
        done=False,
        started=datetime.now(),
        stopped=None,
    )


@router.expose()
async def get_zipping_result(app: FastAPI, task_id: TaskRpcId) -> TaskRpcResult:
    assert app  # nosec
    assert task_id  # nosec
    return TaskRpcResult(result="Here's your result.", error=None)
