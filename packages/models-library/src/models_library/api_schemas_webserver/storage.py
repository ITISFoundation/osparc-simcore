from pathlib import Path

from pydantic import BaseModel

from ..projects_nodes_io import LocationID
from ..rest_pagination import PageQueryParameters
from ._base import InputSchema


class StorageLocationPathParams(BaseModel):
    location_id: LocationID


class ListPathsQueryParams(InputSchema, PageQueryParameters):
    file_filter: Path | None = None
