from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel, model_validator
from servicelib.progress_bar import ProgressBarData
from typing_extensions import Self

AsyncJobId: TypeAlias = UUID


class AsyncJobStatus(BaseModel):
    job_id: AsyncJobId
    progress: ProgressBarData
    done: bool
    started: datetime
    stopped: datetime | None

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        is_done = self.done
        is_stopped = self.stopped is not None

        if is_done != is_stopped:
            msg = f"Inconsistent data: {self.done=}, {self.stopped=}"
            raise ValueError(msg)
        return self


class AsyncJobResult(BaseModel):
    result: Any | None
    error: Any | None


class AsyncJobGet(BaseModel):
    job_id: AsyncJobId
    task_name: str


class AsyncJobAbort(BaseModel):
    result: bool
    job_id: AsyncJobId
