import datetime
from typing import Annotated, Final

from pydantic import BaseModel, ByteSize, ConfigDict, Field
from pydantic.alias_generators import to_camel

from models_library.projects import ProjectID

from .storage_schemas import UNDEFINED_SIZE_TYPE

SEARCH_TASK_NAME: Final[str] = "files_search"


class SearchResultItem(BaseModel):
    name: str
    created_at: Annotated[
        datetime.datetime | None,
        Field(
            description="Creation timestamp. None is possible because of heavy computation required to retrieve this information"
        ),
    ]
    modified_at: Annotated[
        datetime.datetime | None,
        Field(
            description="Last modification timestamp. None is possible because of heavy computation required to retrieve this information"
        ),
    ]
    size: ByteSize | UNDEFINED_SIZE_TYPE
    path: str
    is_directory: bool
    project_id: ProjectID | None

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        validate_by_name=True,
    )
