from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.base import ProgressPercent
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskId,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_storage.zipping_tasks import (
    ZipTaskAbortOutput,
    ZipTaskStartInput,
)
from servicelib.rabbitmq import RPCRouter
from simcore_service_storage.simcore_s3_dsm import TaskProgress

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


@router.expose()
async def get_zipping_status(app: FastAPI, task_id: TaskId) -> TaskStatus:
    progress = TaskProgress(
        task_id=task_id,
        message="Here's a status for you. You are welcome",
        percent=ProgressPercent(0.5),
    )
    return TaskStatus(task_progress=progress, done=False, started=datetime.now())


@router.expose()
async def get_zipping_result(app: FastAPI, task_id: TaskId) -> TaskResult:
    return TaskResult(result="Here's your result.", error=None)
