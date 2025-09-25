import datetime
from pathlib import Path
from typing import Annotated, Final, Self

from models_library.utils.common_validators import (
    MIN_NON_WILDCARD_CHARS,
    WILDCARD_CHARS,
    ensure_pattern_has_enough_characters,
)
from pydantic import BaseModel, Field, model_validator

from ..api_schemas_storage.storage_schemas import (
    DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
    MAX_NUMBER_OF_PATHS_PER_PAGE,
)
from ..projects_nodes_io import LocationID
from ..rest_pagination import CursorQueryParameters
from ._base import InputSchema

MAX_SEARCH_ITEMS_PER_PAGE: Final[int] = 50
DEFAULT_MAX_SEARCH_ITEMS_PER_PAGE: Final[int] = 25


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
    filename_pattern: Annotated[
        str,
        ensure_pattern_has_enough_characters(),
        Field(
            description=f"File name pattern with wildcard support {tuple(WILDCARD_CHARS)}. Minimum of {MIN_NON_WILDCARD_CHARS} non-wildcard characters required.",
        ),
    ]
    last_modified_before: Annotated[
        datetime.datetime | None,
        Field(
            default=None,
            description="Filter results to files modified before this date (inclusive). Format: YYYY-MM-DDTHH:MM:SS",
        ),
    ]
    last_modified_after: Annotated[
        datetime.datetime | None,
        Field(
            default=None,
            description="Filter results to files modified after this date (inclusive). Format: YYYY-MM-DDTHH:MM:SS",
        ),
    ]
    items_per_page: Annotated[
        int,
        Field(
            description="Number of items per page",
            ge=1,
            le=MAX_SEARCH_ITEMS_PER_PAGE,
        ),
    ] = DEFAULT_MAX_SEARCH_ITEMS_PER_PAGE

    @model_validator(mode="after")
    def _validate_date_range(self) -> Self:
        """Ensure that last_modified_before is after last_modified_after when both are present."""
        if (
            self.last_modified_before is not None
            and self.last_modified_after is not None
            and self.last_modified_before <= self.last_modified_after
        ):
            msg = "last_modified_before must be after last_modified_after"
            raise ValueError(msg)
        return self
