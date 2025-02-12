from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.base import (
    ProgressPercent,
    TaskId,
    TaskProgress,
)
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_storage.zipping_tasks import (
    ZipTaskAbortOutput,
    ZipTaskStartInput,
)
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def start_zipping(app: FastAPI, paths: ZipTaskStartInput) -> TaskGet:
    assert app  # nosec
    return TaskGet(
        task_id=f"{uuid4()}",
        task_name=", ".join(str(p) for p in paths.paths),
        status_href="status_url",
        result_href="result url",
        abort_href="abort url",
    )


@router.expose()
async def abort_zipping(app: FastAPI, task_id: TaskId) -> ZipTaskAbortOutput:
    assert app  # nosec
    return ZipTaskAbortOutput(result=True, task_id=task_id)


@router.expose()
async def get_zipping_status(app: FastAPI, task_id: TaskId) -> TaskStatus:
    assert app  # nosec
    progress = TaskProgress(
        task_id=task_id,
        message="Here's a status for you. You are welcome",
        percent=ProgressPercent(0.5),
    )
    return TaskStatus(task_progress=progress, done=False, started=datetime.now())


@router.expose()
async def get_zipping_result(app: FastAPI, task_id: TaskId) -> TaskResult:
    assert app  # nosec
    assert task_id  # nosec
    return TaskResult(result="Here's your result.", error=None)
