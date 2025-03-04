from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, TypeVar

from fastapi import Query
from fastapi_pagination.cursor import CursorPage
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from pydantic import BaseModel, Field

from ..api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from ..api_schemas_storage.data_export_async_jobs import DataExportTaskStartInput
from ..progress_bar import ProgressReport
from ..projects_nodes_io import LocationID, StorageFileID
from ..rest_pagination import (
    CursorQueryParameters,
)
from ._base import InputSchema, OutputSchema

_T = TypeVar("_T")

LargeLimitedPage = CustomizedPage[
    CursorPage[_T],
    # Customizes the maximum value to fit frontend needs
    UseParamsFields(
        size=Query(
            50,
            ge=1,
            le=1000,
            description="Page size",
        )
    ),
]


class StorageLocationPathParams(BaseModel):
    location_id: LocationID


class ListPathsQueryParams(InputSchema, CursorQueryParameters):
    file_filter: Path | None = None

    size: Annotated[
        int,
        Field(
            description="maximum number of items to return (pagination)", ge=1, lt=1000
        ),
    ] = 20


class DataExportPost(InputSchema):
    paths: list[StorageFileID]

    def to_rpc_schema(self, location_id: LocationID) -> DataExportTaskStartInput:
        return DataExportTaskStartInput(
            file_and_folder_ids=self.paths,
            location_id=location_id,
        )


class StorageAsyncJobGet(OutputSchema):
    job_id: AsyncJobId

    @classmethod
    def from_rpc_schema(cls, async_job_rpc_get: AsyncJobGet) -> "StorageAsyncJobGet":
        return StorageAsyncJobGet(job_id=async_job_rpc_get.job_id)


class StorageAsyncJobStatus(OutputSchema):
    job_id: AsyncJobId
    progress: ProgressReport
    done: bool
    started: datetime
    stopped: datetime | None

    @classmethod
    def from_rpc_schema(
        cls, async_job_rpc_status: AsyncJobStatus
    ) -> "StorageAsyncJobStatus":
        return StorageAsyncJobStatus(
            job_id=async_job_rpc_status.job_id,
            progress=async_job_rpc_status.progress,
            done=async_job_rpc_status.done,
            started=async_job_rpc_status.started,
            stopped=async_job_rpc_status.stopped,
        )


class StorageAsyncJobResult(OutputSchema):
    result: Any | None
    error: Any | None

    @classmethod
    def from_rpc_schema(
        cls, async_job_rpc_result: AsyncJobResult
    ) -> "StorageAsyncJobResult":
        return StorageAsyncJobResult(
            result=async_job_rpc_result.result, error=async_job_rpc_result.error
        )
