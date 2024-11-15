""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""

from models_library.projects import ProjectID
from pydantic import BaseModel, Extra, Field

from ..models import RequestContext

assert RequestContext  # nosec


class ProjectPathParams(BaseModel):
    project_id: ProjectID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


class RemoveQueryParams(BaseModel):
    force: bool = Field(
        default=False, description="Force removal (even if resource is active)"
    )


__all__: tuple[str, ...] = ("RequestContext",)
