from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.tasks import TaskGet, TaskId
from models_library.api_schemas_storage.zipping_tasks import (
    ZipTaskAbortOutput,
    ZipTaskStartInput,
)
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def start_zipping(app: FastAPI, paths: ZipTaskStartInput) -> TaskGet:

    return TaskGet(
        task_id=f"{uuid4()}",
        task_name=", ".join(str(p) for p in paths.paths),
        status_href="status_url",
        result_href="result url",
        abort_href="abort url",
    )


@router.expose()
async def abort_zipping(app: FastAPI, task_id: TaskId) -> ZipTaskAbortOutput:
    return ZipTaskAbortOutput(result=True, task_id=task_id)
