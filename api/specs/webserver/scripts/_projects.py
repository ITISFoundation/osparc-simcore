# pylint: disable=unused-argument

from typing import Dict, Union
from uuid import UUID

from __common import Envelope, Page
from fastapi import Path as PathParam
from fastapi import status
from fastapi.param_functions import Query
from fastapi.routing import APIRouter
from pydantic.fields import Field
from pydantic.main import BaseModel
from pydantic.networks import HttpUrl
from pydantic.types import PositiveInt, StrictBool, StrictFloat, StrictInt, constr

# MODELS -----------------------------------------------------------------------------------------

BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]  # order in union matters
DataLink = HttpUrl
DataSchema = Union[BuiltinTypes, DataLink]

InIDStr = OutIDStr = constr(regex=r"^[-_a-zA-Z0-9]+$")
ProjectID = UUID


# DOMAIN MODELS = Resources


class Node(BaseModel):
    key: str
    version: str = Field(..., regex=r"\d+\.\d+\.\d+")
    label: str

    inputs: Dict[InIDStr, DataSchema]
    # var inputs?
    outputs: Dict[OutIDStr, DataSchema]
    # var outputs?


class Project(BaseModel):
    id: ProjectID
    pipeline: Dict[UUID, Node]


# API REQUEST MODELS -> $(ResourceName)In$(RequestName)
class ProjectInNew(BaseModel):
    pipeline: Dict[UUID, Node]


class ProjectInUpdate(BaseModel):
    # same as new but ALL optional??
    # some validators?
    pass


# API RESPONSE MODELS -> $(ResourceName)As$(ResponseFormat)
class ProjectAsItem(BaseModel):
    # Lightweight and part of an array
    id: ProjectID

    url: HttpUrl


class ProjectAsBody(BaseModel):
    id: ProjectID
    pipeline: Dict[UUID, Node]

    url: HttpUrl


# ROUTES -----------------------------------------------------------------------------------------

router = APIRouter()


@router.get("", response_model=Page[ProjectAsItem])
def list_projects(
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


@router.post(
    "", response_model=Envelope[ProjectAsBody], status_code=status.HTTP_201_CREATED
)
def create_project(project: ProjectInNew):
    ...


@router.get("/{project_uuid}", response_model=Envelope[ProjectAsBody])
def get_project(
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier")
):
    ...


@router.put("/{project_uuid}", response_model=Envelope[ProjectAsBody])
def replace_project(
    project: ProjectInNew,
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier"),
):
    ...


@router.patch("/{project_uuid}", response_model=Envelope[ProjectAsBody])
def update_project(
    project: ProjectInUpdate,
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier"),
):
    ...


@router.delete(
    "/{project_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier")
):
    ...


@router.post("/{project_uuid}:open")
def open_project(
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier")
):
    ...


@router.post("/{project_uuid}:start")
def start_project(
    use_cache: bool = True,
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier"),
):
    ...


@router.post("/{project_uuid}:stop")
def stop_project(
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier")
):
    ...


@router.post("/{project_uuid}:close")
def close_project(
    project_uuid: ProjectID = PathParam(..., description="Project unique identifier")
):
    ...
