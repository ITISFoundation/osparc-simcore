#
# assist creating OAS for projects resource
#

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Union
from uuid import UUID

import yaml
from fastapi import FastAPI, status
from pydantic import BaseModel, Field, PositiveInt
from pydantic.networks import AnyUrl

app = FastAPI()

error_responses = {
    status.HTTP_400_BAD_REQUEST: {},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {},
}

BuiltinTypes = Union[bool, int, float, str]
DataSchema = Union[
    BuiltinTypes,
]  # any json schema?
DataLink = AnyUrl

DataSchema = Union[DataSchema, DataLink]


class Node(BaseModel):
    key: str
    version: str = Field(..., regex=r"\d+\.\d+\.\d+")
    label: str

    inputs: Dict[str, DataSchema]
    # var inputs?
    outputs: Dict[str, DataSchema]
    # var outputs?


class Project(BaseModel):
    id: UUID
    pipeline: Dict[UUID, Node]


class ProjectSnapshot(BaseModel):
    id: int
    label: str
    parent_project_id: UUID
    parameters: Dict[str, Any] = {}

    taken_at: Optional[datetime] = Field(
        None,
        description="Timestamp of the time snapshot was taken",
    )


@app.get("/projects/{project_id}")
def get_project(project_id: UUID):
    pass


@app.post("/projects/{project_id}")
def create_project(project: Project):
    pass


@app.put("/projects/{project_id}")
def replace_project(project_id: UUID, project: Project):
    pass


@app.patch("/projects/{project_id}")
def update_project(project_id: UUID, project: Project):
    pass


@app.delete("/projects/{project_id}")
def delete_project(project_id: UUID):
    pass


@app.post("/projects/{project_id}:open")
def open_project(project: Project):
    pass


@app.post("/projects/{project_id}:start")
def start_project(project: Project):
    pass


@app.post("/projects/{project_id}:stop")
def stop_project(project: Project):
    pass


@app.post("/projects/{project_id}:close")
def close_project(project: Project):
    pass


# -------------


@app.get("/projects/{project_id}/snapshots")
async def list_project_snapshots(project_id: UUID):
    pass


@app.post("/projects/{project_id}/snapshots")
async def create_project_snapshot(
    project_id: UUID, snapshot_label: Optional[str] = None
):
    pass


@app.get("/projects/{project_id}/snapshots/{snapshot_id}")
async def get_project_snapshot(project_id: UUID, snapshot_id: PositiveInt):
    pass


@app.get("/projects/{project_id}/snapshots/{snapshot_id}/parameters")
async def get_project_snapshot_parameters(project_id: UUID, snapshot_id: str):
    return {"x": 4, "y": "yes"}


# print(yaml.safe_dump(app.openapi()))
# print("-"*100)


print(json.dumps(app.openapi(), indent=2))

# uvicorn --reload projects_openapi_generator:app
