# pylint: disable=R6301
from pathlib import Path

from models_library.api_schemas_rpc_data_export.async_jobs import AsyncJobRpcId
from models_library.projects_nodes_io import LocationID
from pydantic import BaseModel, Field


class DataExportTaskStartInput(BaseModel):
    location_id: LocationID
    paths: list[Path] = Field(..., min_length=1)


class DataExportTaskAbortOutput(BaseModel):
    result: bool
    task_id: AsyncJobRpcId
