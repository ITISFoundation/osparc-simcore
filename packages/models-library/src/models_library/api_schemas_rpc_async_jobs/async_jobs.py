from typing import Any, TypeAlias
from uuid import UUID

from models_library.users import UserID
from pydantic import BaseModel

from ..progress_bar import ProgressReport

AsyncJobId: TypeAlias = UUID


class AsyncJobStatus(BaseModel):
    job_id: AsyncJobId
    progress: ProgressReport | None
    done: bool


class AsyncJobResult(BaseModel):
    result: Any | None
    error: Any | None


class AsyncJobGet(BaseModel):
    job_id: AsyncJobId


class AsyncJobAbort(BaseModel):
    result: bool
    job_id: AsyncJobId


class AsyncJobNameData(BaseModel):
    """Data for controlling access to an async job"""

    user_id: UserID
    product_name: str
