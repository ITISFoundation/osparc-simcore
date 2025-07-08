from typing import Annotated, Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from ..products import ProductName
from ..progress_bar import ProgressReport
from ..users import UserID

AsyncJobId: TypeAlias = UUID
AsyncJobName: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class AsyncJobFilterBase(BaseModel):
    """Base class for async job filters"""

    model_config = ConfigDict(extra="forbid")


class AsyncJobStatus(BaseModel):
    job_id: AsyncJobId
    progress: ProgressReport
    done: bool


class AsyncJobResult(BaseModel):
    result: Any


class AsyncJobGet(BaseModel):
    job_id: AsyncJobId
    job_name: AsyncJobName


class AsyncJobAbort(BaseModel):
    result: bool
    job_id: AsyncJobId


class AsyncJobFilter(AsyncJobFilterBase):
    """Data for controlling access to an async job"""

    product_name: ProductName
    user_id: UserID
    client_name: Annotated[
        str,
        StringConstraints(min_length=1, pattern=r"^[^\s]+$"),
    ]
