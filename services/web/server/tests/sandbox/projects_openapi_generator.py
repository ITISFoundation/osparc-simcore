#
# Assists on the creation of project's OAS
#
# - Follows https://cloud.google.com/apis/design
#
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from types import FunctionType
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union
from uuid import UUID, uuid3

import simcore_service_webserver.projects.projects_handlers
import simcore_service_webserver.projects.projects_node_handlers
import simcore_service_webserver.snapshots_api_handlers
from fastapi import Depends, FastAPI
from fastapi import Path as PathParam
from fastapi import Query, Request, status
from fastapi.exceptions import HTTPException
from fastapi.routing import APIRoute, APIRouter
from models_library.services import PROPERTY_KEY_RE
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    StrictBool,
    StrictFloat,
    StrictInt,
    constr,
    validator,
)
from pydantic.generics import GenericModel
from pydantic.networks import AnyUrl, HttpUrl
from servicelib.rest_pagination_utils import PageLinks, PageMetaInfoLimitOffset
from simcore_service_webserver.snapshots_models import (
    SnapshotPatchBody,
    SnapshotResource,
)

InputID = OutputID = constr(regex=PROPERTY_KEY_RE)

# WARNING: oder matters
BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]
DataSchema = Union[
    BuiltinTypes,
]  # any json schema?
DataLink = AnyUrl

DataSchema = Union[DataSchema, DataLink]


error_responses = {
    status.HTTP_400_BAD_REQUEST: {},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {},
}

DataT = TypeVar("DataT")


class Error(BaseModel):
    code: int
    message: str


class Envelope(GenericModel, Generic[DataT]):
    data: Optional[DataT]
    error: Optional[Error]

    @validator("error", always=True)
    @classmethod
    def check_consistency(cls, v, values):
        if v is not None and values["data"] is not None:
            raise ValueError("must not provide both data and error")
        if v is None and values.get("data") is None:
            raise ValueError("must provide data or error")
        return v


ItemT = TypeVar("ItemT")

# FIXME: replace PageResponseLimitOffset
# FIXME: page envelope is inconstent since DataT != Page ??
class Page(GenericModel, Generic[ItemT]):
    meta: PageMetaInfoLimitOffset = Field(alias="_meta")
    links: PageLinks = Field(alias="_links")
    data: List[ItemT]


# --------------


class State(BaseModel):
    ...


class Node(BaseModel):
    key: str
    version: str = Field(..., regex=r"\d+\.\d+\.\d+")
    label: str

    inputs: Dict[InputID, DataSchema]
    # var inputs?
    outputs: Dict[OutputID, DataSchema]
    # var outputs?


# --------------
class Project(BaseModel):
    """Domain model"""

    id: UUID
    pipeline: Dict[UUID, Node]


# requests models
class ProjectNew(BaseModel):
    pipeline: Dict[UUID, Node]


class ProjectUpdate(BaseModel):
    # same as new but ALL optional??
    # some validators?
    pass


# response models


class ProjectItem(BaseModel):
    # Lightweight and part of an array
    id: UUID

    url: HttpUrl


class ProjectDetailed(BaseModel):
    id: UUID
    pipeline: Dict[UUID, Node]

    url: HttpUrl

    def update_ids(self, name: str):
        map_ids: Dict[UUID, UUID] = {}
        map_ids[self.id] = uuid3(self.id, name)
        map_ids.update({node_id: uuid3(node_id, name) for node_id in self.pipeline})

        # replace ALL references


class Parameter(BaseModel):
    name: str
    value: BuiltinTypes

    node_id: UUID
    output_id: OutputID


class ParameterResource(Parameter):
    url: AnyUrl
    # url_output: AnyUrl


####################################################################


def get_reverse_url_mapper(request: Request) -> Callable:
    def reverse_url_mapper(name: str, **path_params: Any) -> str:
        return request.url_for(name, **path_params)

    return reverse_url_mapper


_PROJECTS: Dict[UUID, Project] = {}


def get_valid_uuid(project_uuid: UUID = PathParam(...)) -> UUID:
    if project_uuid not in _PROJECTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid id")
    return project_uuid


def redefine_operation_id_in_router(router: APIRouter, operation_id_prefix: str):
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, FunctionType)  # nosec
            route.operation_id = f"{operation_id_prefix}.{route.endpoint.__name__}"


####################################################################

project_routes = APIRouter(prefix="/projects", tags=["project"])


@project_routes.get("/", response_model=Page[ProjectItem])
def list_projects():
    ...


@project_routes.post(
    "/", response_model=Envelope[ProjectDetailed], status_code=status.HTTP_201_CREATED
)
def create_project(project: ProjectNew):
    ...


@project_routes.get("/{project_uuid}", response_model=Envelope[ProjectDetailed])
def get_project(pid: UUID = Depends(get_valid_uuid)):
    ...


@project_routes.put("/{project_uuid}", response_model=Envelope[ProjectDetailed])
def replace_project(project: ProjectNew, pid: UUID = Depends(get_valid_uuid)):
    ...


@project_routes.patch("/{project_uuid}", response_model=Envelope[ProjectDetailed])
def update_project(project: ProjectUpdate, pid: UUID = Depends(get_valid_uuid)):
    ...


@project_routes.delete(
    "/{project_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(pid: UUID = Depends(get_valid_uuid)):
    ...


@project_routes.post(":open")
def open_project(pid: UUID = Depends(get_valid_uuid)):
    ...


@project_routes.post(":start")
def start_project(use_cache: bool = True, pid: UUID = Depends(get_valid_uuid)):
    ...


@project_routes.post(":stop")
def stop_project(pid: UUID = Depends(get_valid_uuid)):
    ...


@project_routes.post(":close")
def close_project(pid: UUID = Depends(get_valid_uuid)):
    ...


redefine_operation_id_in_router(
    project_routes,
    operation_id_prefix=simcore_service_webserver.projects.projects_handlers.__name__,
)

# project states sub-resource

project_states_routes = APIRouter(prefix="/projects/{project_uuid}", tags=["project"])


@project_routes.get("/state", response_model=Envelope[State])
def get_project_state(pid: UUID = Depends(get_valid_uuid)):
    ...


redefine_operation_id_in_router(
    project_states_routes,
    operation_id_prefix=simcore_service_webserver.projects.projects_handlers.__name__,
)

# project nodes sub-resource

project_nodes_routes = APIRouter(prefix="/projects/{project_uuid}", tags=["project"])


@project_nodes_routes.get("/nodes", response_model=Envelope[Node])
def get_project_node(pid: UUID = Depends(get_valid_uuid)):
    ...


redefine_operation_id_in_router(
    project_states_routes,
    operation_id_prefix=simcore_service_webserver.projects.projects_node_handlers.__name__,
)


# project tags sub-resource ---------
# here we use a different approach just to check
class Tags:
    routes = APIRouter(prefix="/projects/{project_uuid}", tags=["project"])

    @staticmethod
    @routes.put("/tags/{tag_id}")
    def replace(tag_id: int, pid: UUID = Depends(get_valid_uuid)):
        """Assigns a tag to a project"""
        ...

    @staticmethod
    @routes.delete(
        "/tags/{tag_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def delete(tag_id: int, pid: UUID = Depends(get_valid_uuid)):
        """Un-assigns tag to a project"""
        ...


# project snapshot
#  - analogous to a git-commit
#  - takes a snapshot of the current state of the project
#  -

snapshot_routes = APIRouter(
    prefix="/projects/{project_uuid}/snapshots", tags=["project", "snapshot"]
)


@snapshot_routes.get(
    "",
    response_model=Page[SnapshotResource],
)
async def list_snapshots(
    pid: UUID = Depends(get_valid_uuid),
    offset: PositiveInt = Query(
        0, description="index to the first item to return (pagination)"
    ),
    limit: int = Query(
        20, description="maximum number of items to return (pagination)", ge=1, le=50
    ),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Lists all snapshots taken from a given project"""


@snapshot_routes.post(
    "",
    response_model=Envelope[SnapshotResource],
    status_code=status.HTTP_201_CREATED,
)
async def create_snapshot(
    pid: UUID = Depends(get_valid_uuid),
    snapshot_label: Optional[str] = None,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Takes a snapshot of the project at this time"""
    # - hash parent_project as a mechanism to check changes
    # -


@snapshot_routes.get(
    "/{snapshot_id}",
    response_model=Envelope[SnapshotResource],
)
async def get_snapshot(
    snapshot_id: PositiveInt,
    pid: UUID = Depends(get_valid_uuid),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Gets commit info for a given snapshot"""


@snapshot_routes.delete(
    "/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_snapshot(
    snapshot_id: PositiveInt,
    pid: UUID = Depends(get_valid_uuid),
):
    """Deletes both the commit and the project itself"""
    # delete a snapshot -> project deleted?
    # delete a project-snapshot -> delete snapshot


@snapshot_routes.patch(
    "/{snapshot_id}",
)
async def update_snapshot(
    snapshot_id: PositiveInt,
    update: SnapshotPatchBody,
    pid: UUID = Depends(get_valid_uuid),
):
    """Updates label/name of a snapshot"""


redefine_operation_id_in_router(
    snapshot_routes,
    operation_id_prefix=simcore_service_webserver.snapshots_api_handlers.__name__,
)
# project parametrization

parameter_routes = APIRouter(
    prefix="/projects/{project_uuid}/parameters", tags=["project"]
)


@parameter_routes.get(
    "",
    response_model=Page[ParameterResource],
)
async def list_project_parameters(
    snapshot_id: str,
    pid: UUID = Depends(get_valid_uuid),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Lists all parameters in a project"""


## workflow compiler #######################################


app = FastAPI(docs_url="/dev/doc")


for routes in [project_routes, project_nodes_routes, snapshot_routes]:
    app.include_router(routes)


# print(yaml.safe_dump(app.openapi()))
# print("-"*100)

with open("openapi-ignore.json", "wt") as f:
    json.dump(app.openapi(), f, indent=2)

# uvicorn --reload projects_openapi_generator:app
