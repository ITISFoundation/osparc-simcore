import datetime
from typing import Literal

from models_library.projects import ProjectID
from pydantic import BaseModel, ByteSize


class SearchResult(BaseModel):
    name: str
    created_at: datetime.datetime
    last_modified: datetime.datetime
    size: ByteSize | Literal[-1]
    path: str
    is_directory: bool
    project_id: ProjectID | None
