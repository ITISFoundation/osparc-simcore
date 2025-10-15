import datetime
from typing import Final, Literal

from models_library.projects import ProjectID
from pydantic import BaseModel, ByteSize, ConfigDict
from pydantic.alias_generators import to_camel

SEARCH_TASK_NAME: Final[str] = "files_search"


class SearchResultItem(BaseModel):
    name: str
    created_at: datetime.datetime
    modified_at: datetime.datetime
    size: ByteSize | Literal[-1]
    path: str
    is_directory: bool
    project_id: ProjectID | None

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        validate_by_name=True,
    )
