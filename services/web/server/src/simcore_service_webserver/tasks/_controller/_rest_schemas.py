from uuid import UUID

from models_library.rest_pagination import PageQueryParameters
from pydantic import BaseModel, ConfigDict


class TaskPathParams(BaseModel):
    task_id: UUID
    model_config = ConfigDict(extra="forbid", frozen=True)


class TaskStreamQueryParams(PageQueryParameters): ...
