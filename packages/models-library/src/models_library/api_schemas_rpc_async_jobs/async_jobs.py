from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID

from models_library.users import UserID
from pydantic import BaseModel, model_validator
from typing_extensions import Self

from ..progress_bar import ProgressReport

AsyncJobId: TypeAlias = UUID


class AsyncJobStatus(BaseModel):
    job_id: AsyncJobId
    progress: ProgressReport
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
    job_name: str


class AsyncJobAbort(BaseModel):
    result: bool
    job_id: AsyncJobId


class AsyncJobAccessData(BaseModel):
    """Data for controlling access to an async job"""

    user_id: UserID | None
    product_name: str
