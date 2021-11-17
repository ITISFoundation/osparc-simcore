# pylint: disable=unused-argument

from datetime import datetime
from typing import List, Optional

from __common import Envelope, Page
from _projects import BuiltinTypes, ProjectID
from _projects_repos import RefID
from fastapi import Path as PathParam
from fastapi.param_functions import Query
from fastapi.routing import APIRouter
from pydantic.fields import Field
from pydantic.main import BaseModel
from pydantic.networks import HttpUrl
from pydantic.types import PositiveInt, constr

# MODELS -----------------------------------------------------------------------------------------

IterID = int  # order ?


class ParameterItem(BaseModel):
    display_name: str
    value: Optional[BuiltinTypes] = None

    port_url: HttpUrl


class IterationAsItem(BaseModel):
    uid: IterID

    # parent
    #  {
    # project_uuid: ProjectID
    # ref_id: RefID
    # }

    wcopy_project_uuid: ProjectID = Field(
        ...,
        description="ID to this iteration's working copy."
        "A working copy is a real project where this iteration is run",
    )
    # an project-id with a view i.e. read-only??

    # updated? this will change with time ....
    parameters: List[ParameterItem]
    probes: List[ParameterItem]

    # updated: datetime

    wcopy_project_url: HttpUrl  # should be read-only!
    url: HttpUrl


class IterationAsBody(IterationAsItem):
    ...


# ROUTES -----------------------------------------------------------------------------------------

router = APIRouter()


@router.get(
    "/{project_uuid}/checkpoint/{ref_id}/iterations",
    response_model=Page[IterationAsItem],
)
def list_project_iterations(
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier"),
    ref_id: RefID = PathParam(...),
    offset: PositiveInt = Query(
        0, description="index to the first item to return (pagination)"
    ),
    limit: int = Query(
        20,
        description="maximum number of items to return (pagination)",
        ge=1,
        le=50,
    ),
):
    ...


@router.get(
    "/{project_uuid}/checkpoint/{ref_id}/iterations/{iter_id}",
    response_model=Envelope[IterationAsBody],
)
def get_project_iteration(
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier"),
    ref_id: RefID = PathParam(...),
    iter_id: IterID = PathParam(...),
):
    ...
