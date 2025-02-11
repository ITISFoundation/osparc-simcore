# pylint: disable=R6301
from pathlib import Path

from pydantic import BaseModel, model_validator
from simcore_service_storage.api.rabbitmq_rpc._zipping import TaskId


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
