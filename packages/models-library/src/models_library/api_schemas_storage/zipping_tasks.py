# pylint: disable=R6301
from pathlib import Path

from models_library.api_schemas_rpc_long_running_tasks.tasks import TaskRpcId
from pydantic import BaseModel, Field


class ZipTaskStartInput(BaseModel):
    paths: list[Path] = Field(..., min_length=1)


class ZipTaskAbortOutput(BaseModel):
    result: bool
    task_id: TaskRpcId
