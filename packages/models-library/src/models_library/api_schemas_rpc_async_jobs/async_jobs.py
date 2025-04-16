from typing import Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel

from ..products import ProductName
from ..progress_bar import ProgressReport
from ..users import UserID

AsyncJobId: TypeAlias = UUID
AsyncJobName: TypeAlias = str


class AsyncJobStatus(BaseModel):
    job_id: AsyncJobId
    progress: ProgressReport
    done: bool


class AsyncJobResult(BaseModel):
    result: Any


class AsyncJobGet(BaseModel):
    job_id: AsyncJobId
    job_name: AsyncJobName | None


class AsyncJobAbort(BaseModel):
    result: bool
    job_id: AsyncJobId


class AsyncJobNameData(BaseModel):
    """Data for controlling access to an async job"""

    product_name: ProductName
    user_id: UserID
