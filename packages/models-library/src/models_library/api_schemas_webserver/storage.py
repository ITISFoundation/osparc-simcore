import datetime
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from models_library.projects import ProjectID
from models_library.utils.common_validators import (
    MIN_NON_WILDCARD_CHARS,
    WILDCARD_CHARS,
    ensure_pattern_has_enough_characters_before,
)

from ..api_schemas_storage.storage_schemas import (
    DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
    MAX_NUMBER_OF_PATHS_PER_PAGE,
)
from ..projects_nodes_io import LocationID, SimcoreS3FileID
from ..rest_pagination import CursorQueryParameters
from ._base import InputSchema


class StorageLocationPathParams(BaseModel):
    location_id: LocationID


class StoragePathComputeSizeParams(StorageLocationPathParams):
    path: Path


class StoragePathRefreshParams(StorageLocationPathParams):
    s3_directory: SimcoreS3FileID


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


class SearchTimerangeFilter(InputSchema):
    from_: Annotated[
        datetime.datetime | None,
        Field(
            alias="from",
            description="Filter results before this date",
        ),
    ] = None
    until: Annotated[
        datetime.datetime | None,
        Field(
            description="Filter results after this date",
        ),
    ] = None

    @model_validator(mode="after")
    def _validate_date_range(self) -> Self:
        if self.from_ is not None and self.until is not None and self.from_ > self.until:
            msg = f"Invalid date range: '{self.from_}' must be before '{self.until}'"
            raise ValueError(msg)
        return self


class SearchFilters(InputSchema):
    name_pattern: Annotated[
        str,
        ensure_pattern_has_enough_characters_before(),
        Field(
            description=f"Name pattern with wildcard support ({', '.join(WILDCARD_CHARS)}). "
            f"Minimum of {MIN_NON_WILDCARD_CHARS} non-wildcard characters required.",
        ),
    ]
    modified_at: Annotated[
        SearchTimerangeFilter | None,
        Field(
            description="Filter results based on modification date range",
        ),
    ] = None
    project_id: Annotated[
        ProjectID | None,
        Field(
            description="If provided, only files within this project are searched",
        ),
    ] = None


class SearchBodyParams(InputSchema):
    filters: SearchFilters
