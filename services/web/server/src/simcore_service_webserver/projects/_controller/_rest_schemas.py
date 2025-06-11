from models_library.projects import ProjectID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from ...models import AuthenticatedRequestContext

assert AuthenticatedRequestContext.__name__  # nosec


class ProjectPathParams(BaseModel):
    project_id: ProjectID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class RemoveQueryParams(BaseModel):
    force: bool = Field(
        default=False, description="Force removal (even if resource is active)"
    )


__all__: tuple[str, ...] = ("AuthenticatedRequestContext",)
