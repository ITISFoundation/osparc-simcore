from uuid import UUID

from pydantic import BaseModel
from simcore_service_webserver.models import ConfigDict


class TaskPathParams(BaseModel):
    task_id: UUID
    model_config = ConfigDict(extra="forbid", frozen=True)
