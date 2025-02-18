from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from ..api_schemas_storage.rpc.data_export_async_jobs import DataExportTaskStartInput
from ..progress_bar import ProgressReport
from ..projects_nodes_io import LocationID
from ..users import UserID


class DataExportPost(BaseModel):
    paths: list[Path]

    def to_storage_model(
        self, user_id: UserID, location_id: LocationID
    ) -> DataExportTaskStartInput:
        return DataExportTaskStartInput(
            paths=self.paths, user_id=user_id, location_id=location_id
        )


class StorageAsyncJobGet(BaseModel):
    job_id: AsyncJobId

    @classmethod
    def from_async_job_rpc_get(
        cls, async_job_rpc_get: AsyncJobGet
    ) -> "StorageAsyncJobGet":
        return StorageAsyncJobGet(job_id=async_job_rpc_get.job_id)


class StorageAsyncJobStatus(BaseModel):
    job_id: AsyncJobId
    progress: ProgressReport
    done: bool
    started: datetime
    stopped: datetime | None

    @classmethod
    def from_async_job_rpc_status(
        cls, async_job_rpc_status: AsyncJobStatus
    ) -> "StorageAsyncJobStatus":
        return StorageAsyncJobStatus(
            job_id=async_job_rpc_status.job_id,
            progress=async_job_rpc_status.progress,
            done=async_job_rpc_status.done,
            started=async_job_rpc_status.started,
            stopped=async_job_rpc_status.stopped,
        )


class StorageAsyncJobResult(BaseModel):
    result: Any | None
    error: Any | None

    @classmethod
    def from_async_job_rpc_result(
        cls, async_job_rpc_result: AsyncJobResult
    ) -> "StorageAsyncJobResult":
        return StorageAsyncJobResult(
            result=async_job_rpc_result.result, error=async_job_rpc_result.error
        )
