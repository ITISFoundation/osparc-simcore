# pylint: disable=R6301
from pathlib import Path

from models_library.api_schemas_long_running_tasks.base import TaskId
from pydantic import BaseModel, model_validator


class ZipTaskStartInput(BaseModel):
    paths: list[Path]

    @model_validator(mode="after")
    def _check_paths(self, value):
        if not value:
            raise ValueError("Empty paths error")
        return value


class ZipTaskAbortOutput(BaseModel):
    result: bool
    task_id: TaskId
