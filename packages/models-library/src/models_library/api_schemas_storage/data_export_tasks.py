# pylint: disable=R6301
from pathlib import Path

from models_library.api_schemas_rpc_data_export.tasks import TaskRpcId
from pydantic import BaseModel, Field


class DataExportTaskStartInput(BaseModel):
    paths: list[Path] = Field(..., min_length=1)


class DataExportTaskAbortOutput(BaseModel):
    result: bool
    task_id: TaskRpcId
