# pylint: disable=unused-argument

from datetime import datetime
from typing import List, Optional

from __common import Envelope, Page
from _projects import BuiltinTypes, ProjectID
from _projects_repos import RefID
from fastapi import Path as PathParam
from fastapi import status
from fastapi.param_functions import Query
from fastapi.routing import APIRouter
from pydantic.fields import Field
from pydantic.main import BaseModel
from pydantic.networks import HttpUrl
from pydantic.types import PositiveInt

# MODELS -----------------------------------------------------------------------------------------

IterID = int  # order ?


class ParameterItem(BaseModel):
    display_name: str
    value: Optional[BuiltinTypes] = None

    port_url: HttpUrl


class ParentMetaProjectRef(BaseModel):
    project_id: ProjectID
    ref_id: int


class IterationAsItem(BaseModel):
    name: str = Field(
        ...,
        description="Iteration's resource name [AIP-122](https://google.aip.dev/122)",
    )
    parent: ParentMetaProjectRef = Field(
        ..., description="Reference to the the meta-project that defines this iteration"
    )

    wcopy_project_id: ProjectID = Field(
        ...,
        description="ID to this iteration's working copy."
        "A working copy is a real project where this iteration is run",
    )

    wcopy_project_url: HttpUrl  # should be read-only!
    url: HttpUrl  # self


class IterationAsBody(IterationAsItem):
    parameters: Optional[List[ParameterItem]] = None
    probes: Optional[List[ParameterItem]] = None


# ROUTES -----------------------------------------------------------------------------------------

router = APIRouter()


@router.get(
    "/{project_uuid}/checkpoint/{ref_id}/iterations",
    response_model=Page[IterationAsItem],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "This project has no iterations."
            "Only meta-project have iterations and they must be explicitly created."
        },
    },
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
    """Lists current project's iterations"""
    ...


@router.post(
    "/{project_uuid}/checkpoint/{ref_id}/iterations",
    response_model=Page[IterationAsItem],
)
def create_project_iterations(
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
    """Gets or creates projects iterations

    If the number of iterations is not bound (e.g. in an optimization) then it responds
    when the requested range (offset: offset+limits)
    """
    ...


if 0:

    @router.get(
        "/{project_uuid}/checkpoint/{ref_id}/iterations/{iter_id}",
        response_model=Envelope[IterationAsBody],
    )
    def get_project_iteration(
        project_uuid: ProjectID = PathParam(
            ..., description="Project unique identifier"
        ),
        ref_id: RefID = PathParam(...),
        iter_id: IterID = PathParam(...),
    ):
        ...
