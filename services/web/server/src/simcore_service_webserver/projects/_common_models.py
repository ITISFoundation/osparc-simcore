""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""

from models_library.projects import ProjectID
from pydantic import BaseModel, ConfigDict, Field

from ..models import RequestContext

assert RequestContext.__name__  # nosec


class ProjectPathParams(BaseModel):
    project_id: ProjectID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class RemoveQueryParams(BaseModel):
    force: bool = Field(
        default=False, description="Force removal (even if resource is active)"
    )


__all__: tuple[str, ...] = ("RequestContext",)
