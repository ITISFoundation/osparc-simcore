from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.base import (
    ProgressPercent,
    TaskProgress,
)
from models_library.api_schemas_long_running_tasks.tasks import TaskStatus
from models_library.api_schemas_storage.zipping_tasks import ZipTaskStart
from pydantic import ValidationError
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose(reraise_if_error_type=(ValidationError,))
async def start_zipping(app: FastAPI, paths: ZipTaskStart) -> TaskStatus:

    progress = TaskProgress(
        task_id=f"{uuid4()}",
        message=", ".join(str(p) for p in paths.paths),
        percent=ProgressPercent(0.5),
    )
    return TaskStatus(task_progress=progress, done=False, started=datetime.now())
