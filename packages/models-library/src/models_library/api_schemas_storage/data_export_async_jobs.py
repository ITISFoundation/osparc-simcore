# pylint: disable=R6301
from pathlib import Path

from models_library.projects_nodes_io import LocationID
from pydantic import BaseModel, Field


class DataExportTaskStartInput(BaseModel):
    location_id: LocationID
    paths: list[Path] = Field(..., min_length=1)
