from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from ..api_schemas_storage.storage_schemas import (
    DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
    MAX_NUMBER_OF_PATHS_PER_PAGE,
)
from ..projects_nodes_io import LocationID
from ..rest_pagination import CursorQueryParameters
from ._base import InputSchema


class StorageLocationPathParams(BaseModel):
    location_id: LocationID


class StoragePathComputeSizeParams(StorageLocationPathParams):
    path: Path


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


class BatchDeletePathsBodyParams(InputSchema):
    paths: set[Path]


PathToExport = Path


class DataExportPost(InputSchema):
    paths: list[PathToExport]


class SearchBodyParams(InputSchema):
    name_pattern: str
