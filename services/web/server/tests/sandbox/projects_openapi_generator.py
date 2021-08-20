#
# Assists on the creation of project's OAS
#

import json

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID, uuid3

import simcore_service_webserver.projects.projects_handlers
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
)
from pydantic.networks import AnyUrl
from simcore_service_webserver.snapshots_models import (
    SnapshotPatchBody,
    SnapshotResource,
)

logging.basicConfig(level=logging.DEBUG)


error_responses = {
    status.HTTP_400_BAD_REQUEST: {},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {},
}


InputID = OutputID = constr(regex=PROPERTY_KEY_RE)

# WARNING: oder matters
BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]
DataSchema = Union[
    BuiltinTypes,
]  # any json schema?
DataLink = AnyUrl

DataSchema = Union[DataSchema, DataLink]


class Node(BaseModel):
    key: str
    version: str = Field(..., regex=r"\d+\.\d+\.\d+")
    label: str

    inputs: Dict[InputID, DataSchema]
    # var inputs?
    outputs: Dict[OutputID, DataSchema]
    # var outputs?


class Project(BaseModel):
    id: UUID
    pipeline: Dict[UUID, Node]

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


_PROJECTS: Dict[UUID, Project] = {}


####################################################################


def get_reverse_url_mapper(request: Request) -> Callable:
    def reverse_url_mapper(name: str, **path_params: Any) -> str:
        return request.url_for(name, **path_params)

    return reverse_url_mapper


def get_valid_uuid(project_uuid: UUID = PathParam(...)) -> UUID:
    if project_uuid not in _PROJECTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid id")
    return project_uuid


####################################################################

project_routes = APIRouter(tags=["project"])


@project_routes.get(
    "/projects/{project_uuid}", response_model=Project, tags=["project"]
)
def get_project(pid: UUID = Depends(get_valid_uuid)):
    return _PROJECTS[pid]


@project_routes.post(
    "/projects/{project_uuid}", status_code=status.HTTP_201_CREATED, tags=["project"]
)
def create_project(project: Project):
    if project.id not in _PROJECTS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invalid id")
    _PROJECTS[project.id] = project


@project_routes.put("/projects/{project_uuid}", tags=["project"])
def replace_project(project: Project, pid: UUID = Depends(get_valid_uuid)):
    _PROJECTS[pid] = project


@project_routes.patch("/projects/{project_uuid}", tags=["project"])
def update_project(project: Project, pid: UUID = Depends(get_valid_uuid)):
    raise NotImplementedError()


@project_routes.delete("/projects/{project_uuid}", tags=["project"])
def delete_project(pid: UUID = Depends(get_valid_uuid)):
    del _PROJECTS[pid]


@project_routes.post("/projects/{project_uuid}:open", tags=["project"])
def open_project(pid: UUID = Depends(get_valid_uuid)):
    pass


@project_routes.post("/projects/{project_uuid}:start", tags=["project"])
def start_project(use_cache: bool = True, pid: UUID = Depends(get_valid_uuid)):
    pass


@project_routes.post("/projects/{project_uuid}:stop", tags=["project"])
def stop_project(pid: UUID = Depends(get_valid_uuid)):
    pass


@project_routes.post("/projects/{project_uuid}:close", tags=["project"])
def close_project(pid: UUID = Depends(get_valid_uuid)):
    pass


# project snapshot
#  - analogous to a git-commit
#  - takes a snapshot of the current state of the project
#  -

snapshot_routes = APIRouter(tags=["project", "snapshot"])


@snapshot_routes.get(
    "/projects/{project_uuid}/snapshots",
    response_model=List[SnapshotResource],
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
    "/projects/{project_uuid}/snapshots",
    response_model=SnapshotResource,
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
    "/projects/{project_uuid}/snapshots/{snapshot_id}",
    response_model=SnapshotResource,
)
async def get_snapshot(
    snapshot_id: PositiveInt,
    pid: UUID = Depends(get_valid_uuid),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Gets commit info for a given snapshot"""


@snapshot_routes.delete(
    "/projects/{project_uuid}/snapshots/{snapshot_id}",
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
    "/projects/{project_uuid}/snapshots/{snapshot_id}",
)
async def update_snapshot(
    snapshot_id: PositiveInt,
    update: SnapshotPatchBody,
    pid: UUID = Depends(get_valid_uuid),
):
    """Updates label/name of a snapshot"""


# project parametrization

parameter_routes = APIRouter(tags=["project"])


@parameter_routes.get(
    "/projects/{project_uuid}/parameters",
    response_model=List[ParameterResource],
)
async def list_snapshot_parameters(
    snapshot_id: str,
    pid: UUID = Depends(get_valid_uuid),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Lists all parameters in a project"""


## workflow compiler #######################################


def redifine_operation_id_in_router(router: APIRouter, operation_id_prefix: str):
    for route in router.routes:
        if isinstance(route, APIRoute):
            route.operation_id = f"{operation_id_prefix}.{route.endpoint.__name__}"


def include_router(app: FastAPI, router: APIRouter, operation_id_prefix: str):
    redifine_operation_id_in_router(router, operation_id_prefix)
    app.include_router(router)


app = FastAPI(docs_url="/dev/doc")


include_router(
    app,
    project_routes,
    operation_id_prefix=simcore_service_webserver.projects.projects_handlers.__name__,
)
include_router(
    app,
    snapshot_routes,
    operation_id_prefix=simcore_service_webserver.snapshots_api_handlers.__name__,
)
# app.include_router(parameter_routes)


# print(yaml.safe_dump(app.openapi()))
# print("-"*100)

with open("openapi-ignore.json", "wt") as f:
    json.dump(app.openapi(), f, indent=2)

# uvicorn --reload projects_openapi_generator:app
