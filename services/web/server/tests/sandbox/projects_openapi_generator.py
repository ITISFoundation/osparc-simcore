#
# Assists on the creation of project's OAS
#

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID, uuid3

from fastapi import Depends, FastAPI
from fastapi import Path as PathParam
from fastapi import Query, Request, status
from fastapi.exceptions import HTTPException
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

app = FastAPI()

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


class Snapshot(BaseModel):
    id: PositiveInt = Field(..., description="Unique snapshot identifier")
    label: Optional[str] = Field(None, description="Unique human readable display name")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the time snapshot was taken from parent. Notice that parent might change with time",
    )

    parent_uuid: UUID = Field(..., description="Parent's project uuid")
    project_uuid: UUID = Field(..., description="Current project's uuid")


class ParameterApiModel(Parameter):
    url: AnyUrl
    # url_output: AnyUrl


class SnapshotApiModel(Snapshot):
    url: AnyUrl
    url_parent: AnyUrl
    url_project: AnyUrl
    url_parameters: Optional[AnyUrl] = None


####################################################################


_PROJECTS: Dict[UUID, Project] = {}


####################################################################


def get_reverse_url_mapper(request: Request) -> Callable:
    def reverse_url_mapper(name: str, **path_params: Any) -> str:
        return request.url_for(name, **path_params)

    return reverse_url_mapper


def get_valid_id(project_id: UUID = PathParam(...)) -> UUID:
    if project_id not in _PROJECTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid id")
    return project_id


####################################################################


@app.get("/projects/{project_id}", response_model=Project, tags=["project"])
def get_project(pid: UUID = Depends(get_valid_id)):
    return _PROJECTS[pid]


@app.post(
    "/projects/{project_id}", status_code=status.HTTP_201_CREATED, tags=["project"]
)
def create_project(project: Project):
    if project.id not in _PROJECTS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invalid id")
    _PROJECTS[project.id] = project


@app.put("/projects/{project_id}", tags=["project"])
def replace_project(project: Project, pid: UUID = Depends(get_valid_id)):
    _PROJECTS[pid] = project


@app.patch("/projects/{project_id}", tags=["project"])
def update_project(project: Project, pid: UUID = Depends(get_valid_id)):
    raise NotImplementedError()


@app.delete("/projects/{project_id}", tags=["project"])
def delete_project(pid: UUID = Depends(get_valid_id)):
    del _PROJECTS[pid]


@app.post("/projects/{project_id}:open", tags=["project"])
def open_project(pid: UUID = Depends(get_valid_id)):
    pass


@app.post("/projects/{project_id}:start", tags=["project"])
def start_project(use_cache: bool = True, pid: UUID = Depends(get_valid_id)):
    pass


@app.post("/projects/{project_id}:stop", tags=["project"])
def stop_project(pid: UUID = Depends(get_valid_id)):
    pass


@app.post("/projects/{project_id}:close", tags=["project"])
def close_project(pid: UUID = Depends(get_valid_id)):
    pass


# project snapshot
#  - analogous to a git-commit
#  - takes a snapshot of the current state of the project
#  -


@app.get(
    "/projects/{project_id}/snapshots",
    response_model=List[SnapshotApiModel],
    tags=["project"],
)
async def list_snapshots(
    pid: UUID = Depends(get_valid_id),
    offset: PositiveInt = Query(
        0, description="index to the first item to return (pagination)"
    ),
    limit: int = Query(
        20, description="maximum number of items to return (pagination)", ge=1, le=50
    ),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Lists all snapshots taken from a given project """


@app.post(
    "/projects/{project_id}/snapshots",
    response_model=SnapshotApiModel,
    status_code=status.HTTP_201_CREATED,
    tags=["project"],
)
async def create_snapshot(
    pid: UUID = Depends(get_valid_id),
    snapshot_label: Optional[str] = None,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Takes a snapshot of the project at this time """
    # - hash parent_project as a mechanism to check changes
    # -


@app.get(
    "/projects/{project_id}/snapshots/{snapshot_id}",
    response_model=SnapshotApiModel,
    tags=["project"],
)
async def get_snapshot(
    snapshot_id: PositiveInt,
    pid: UUID = Depends(get_valid_id),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Gets commit info for a given snapshot """


@app.delete(
    "/projects/{project_id}/snapshots/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["project"],
)
async def delete_snapshot(
    snapshot_id: PositiveInt,
    pid: UUID = Depends(get_valid_id),
):
    """ Deletes both the commit and the project itself """
    # delete a snapshot -> project deleted?
    # delete a project-snapshot -> delete snapshot


@app.get(
    "/projects/{project_id}/snapshots/{snapshot_id}/parameters",
    response_model=List[ParameterApiModel],
    tags=["project"],
)
async def list_snapshot_parameters(
    snapshot_id: str,
    pid: UUID = Depends(get_valid_id),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    pass


## workflow compiler #######################################

# print(yaml.safe_dump(app.openapi()))
# print("-"*100)


with open("openapi-ignore.json", "wt") as f:
    json.dump(app.openapi(), f, indent=2)

# uvicorn --reload projects_openapi_generator:app
