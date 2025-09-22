import datetime
from typing import Literal

from models_library.projects import ProjectID
from pydantic import BaseModel, ByteSize


class SearchResult(BaseModel):
    name: str
    created_at: datetime.datetime
    modified_at: datetime.datetime
    size: ByteSize | Literal[-1]
    is_directory: bool
    project_id: ProjectID | None
