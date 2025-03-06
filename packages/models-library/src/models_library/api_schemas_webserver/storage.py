from pathlib import Path
from typing import Annotated, Any

from aiohttp import web
from models_library.api_schemas_storage.storage_schemas import (
    DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
    MAX_NUMBER_OF_PATHS_PER_PAGE,
)
from pydantic import BaseModel, Field, HttpUrl

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


class StorageLocationPathParams(BaseModel):
    location_id: LocationID


class ListPathsQueryParams(InputSchema, CursorQueryParameters):
    file_filter: Path | None = None

    size: Annotated[
        int,
        Field(
            description="maximum number of items to return (pagination)",
            ge=1,
            lt=MAX_NUMBER_OF_PATHS_PER_PAGE,
        ),
    ] = DEFAULT_NUMBER_OF_PATHS_PER_PAGE


class DataExportPost(InputSchema):
    paths: list[StorageFileID]

    def to_rpc_schema(self, location_id: LocationID) -> DataExportTaskStartInput:
        return DataExportTaskStartInput(
            file_and_folder_ids=self.paths,
            location_id=location_id,
        )


class AsyncJobLinks(OutputSchema):
    status_href: HttpUrl
    abort_href: HttpUrl
    result_href: HttpUrl


class StorageAsyncJobGet(OutputSchema):
    job_id: AsyncJobId
    links: AsyncJobLinks

    @classmethod
    def from_rpc_schema(
        cls, app: web.Application, async_job_rpc_get: AsyncJobGet
    ) -> "StorageAsyncJobGet":
        job_id = f"{async_job_rpc_get.job_id}"
        links = AsyncJobLinks(
            status_href=HttpUrl(
                f"{app.router['get_async_job_status'].url_for(job_id=job_id)}"
            ),
            abort_href=HttpUrl(
                f"{app.router['abort_async_job'].url_for(job_id=job_id)}"
            ),
            result_href=HttpUrl(
                f"{app.router['get_async_job_result'].url_for(job_id=job_id)}"
            ),
        )
        return StorageAsyncJobGet(job_id=async_job_rpc_get.job_id, links=links)


class StorageAsyncJobStatus(OutputSchema):
    job_id: AsyncJobId
    progress: ProgressReport
    done: bool

    @classmethod
    def from_rpc_schema(
        cls, async_job_rpc_status: AsyncJobStatus
    ) -> "StorageAsyncJobStatus":
        return StorageAsyncJobStatus(
            job_id=async_job_rpc_status.job_id,
            progress=async_job_rpc_status.progress,
            done=async_job_rpc_status.done,
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
