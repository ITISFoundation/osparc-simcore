import datetime
from typing import Literal

from models_library.api_schemas_webserver._base import OutputSchema
from models_library.projects import ProjectID
from pydantic import ByteSize


class SearchResult(OutputSchema):
    name: str
    created_at: datetime.datetime
    last_modified: datetime.datetime
    size: ByteSize | Literal[-1]
    is_directory: bool
    project_id: ProjectID | None
