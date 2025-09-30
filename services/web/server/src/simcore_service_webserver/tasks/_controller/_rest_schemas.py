from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskPathParams(BaseModel):
    task_id: UUID
    model_config = ConfigDict(extra="forbid", frozen=True)
