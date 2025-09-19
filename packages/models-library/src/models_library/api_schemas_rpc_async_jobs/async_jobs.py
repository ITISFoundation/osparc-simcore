from typing import Annotated, Any, TypeAlias
from uuid import UUID

from models_library.products import ProductName
from models_library.users import UserID
from pydantic import BaseModel, ConfigDict, StringConstraints

from ..progress_bar import ProgressReport

AsyncJobId: TypeAlias = UUID
AsyncJobName: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


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


class AsyncJobOwnerMetadata(BaseModel):
    """Data for controlling access to an async job"""

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "product_name": "osparc",
                    "user_id": 123,
                    "owner": "web_client",
                }
            ]
        },
    )
    user_id: UserID
    product_name: ProductName
    owner: Annotated[str, StringConstraints(min_length=1, pattern=r"^[a-z_-]+$")]
