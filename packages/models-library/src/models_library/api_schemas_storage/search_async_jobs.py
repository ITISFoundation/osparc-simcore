import datetime

from models_library.projects import ProjectID
from pydantic import BaseModel


class SearchResult(BaseModel):
    name: str
    project_id: ProjectID | None
    created_at: datetime.datetime
    modified_at: datetime.datetime
    is_directory: bool
