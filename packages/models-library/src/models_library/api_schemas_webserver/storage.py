from pathlib import Path
from typing import Annotated, Final

from pydantic import BaseModel, BeforeValidator, Field

from ..api_schemas_storage.storage_schemas import (
    DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
    MAX_NUMBER_OF_PATHS_PER_PAGE,
)
from ..projects_nodes_io import LocationID
from ..rest_pagination import CursorQueryParameters
from ._base import InputSchema

MIN_NON_WILDCARD_CHARS: Final[int] = 3

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


def validate_pattern_has_enough_characters(v: str) -> str:
    non_wildcard_chars = len([c for c in v if c not in ("*", "?")])

    if non_wildcard_chars < MIN_NON_WILDCARD_CHARS:
        msg = f"Name pattern must contain at least {MIN_NON_WILDCARD_CHARS} non-wildcard characters (not * or ?), got {non_wildcard_chars}"
        raise ValueError(msg)
    return v


class SearchBodyParams(InputSchema):
    name_pattern: Annotated[
         str,
         BeforeValidator(validate_pattern_has_enough_characters),
         Field(
              description="Name pattern with wildcard support (* and ?). Minimum of {MIN_NON_WILDCARD_CHARS} non-wildcard characters required.",
         )
    ]
