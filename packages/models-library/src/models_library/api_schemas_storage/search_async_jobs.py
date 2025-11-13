import datetime
from typing import Final

from models_library.projects import ProjectID
from pydantic import BaseModel, ByteSize, ConfigDict
from pydantic.alias_generators import to_camel

from .storage_schemas import UNDEFINED_SIZE_TYPE

SEARCH_TASK_NAME: Final[str] = "files_search"


class SearchResultItem(BaseModel):
    name: str
    created_at: datetime.datetime | None
    modified_at: datetime.datetime | None
    size: ByteSize | UNDEFINED_SIZE_TYPE
    path: str
    is_directory: bool
    project_id: ProjectID | None

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        validate_by_name=True,
    )
