from uuid import UUID

from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
)
from pydantic import BaseModel, ConfigDict


class TaskPathParams(BaseModel):
    task_id: UUID
    model_config = ConfigDict(extra="forbid", frozen=True)


class TaskStreamQueryParams(BaseModel):
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE


class TaskStreamResponse(BaseModel):
    items: list[dict]
    end: bool
    model_config = ConfigDict(extra="forbid", frozen=True)
