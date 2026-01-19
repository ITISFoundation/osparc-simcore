from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from ..progress_bar import ProgressReport

type AsyncJobId = UUID
type AsyncJobName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AsyncJobStatus(BaseModel):
    job_id: AsyncJobId
    progress: ProgressReport
    done: bool


class AsyncJobResult(BaseModel):
    result: Any


class AsyncJobGet(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "job_name": "export_data_task",
                }
            ]
        }
    )

    job_id: AsyncJobId
    job_name: AsyncJobName


class AsyncJobAbort(BaseModel):
    result: bool
    job_id: AsyncJobId
