# pylint: disable=unused-argument

from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

from __common import Envelope, Page
from _projects import Node, ProjectID
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Query
from fastapi.routing import APIRouter
from pydantic.main import BaseModel
from pydantic.networks import HttpUrl
from pydantic.types import PositiveInt, constr

# MODELS -----------------------------------------------------------------------------------------

SHA1Str = constr(regex=r"^[a-fA-F0-9]{40}$")

RepoID = int
CommitID = int
BranchID = int
RefID = Union[CommitID, str]


class RepoAsItem(BaseModel):
    project_uuid: ProjectID

    project_url: HttpUrl
    checkpoints_url: HttpUrl


class Checkpoint(BaseModel):
    id: PositiveInt
    checksum: SHA1Str
    created_at: datetime
    tags: Tuple[str, ...]

    message: Optional[str] = None
    parents_ids: Tuple[PositiveInt, ...] = None  # type: ignore


class CheckpointInUpdate(BaseModel):
    # all updatable items -> annotations
    tags: Optional[Tuple[str, ...]] = None
    message: Optional[str] = None


class CheckpointAsItem(Checkpoint):
    # might want to remove some secret/internals?
    pass


class CheckpointAsBody(Checkpoint):
    url: HttpUrl


class ProjectWorkbenchViewAsBody(BaseModel):
    workbench: Dict[str, Node]
    ui: Dict[str, Any] = {}

    checkpoint_url: HttpUrl
    url: HttpUrl


# ROUTES -----------------------------------------------------------------------------------------

router = APIRouter()


@router.get("/repos", response_model=Page[RepoAsItem])
def list_versioned_projects(
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
    "/{project_uuid}/checkpoints",
    response_model=Envelope[CheckpointAsBody],
    status_code=status.HTTP_201_CREATED,
)
def create_project_checkpoint(project_uuid: ProjectID):
    ...


@router.get("/{project_uuid}/checkpoints", response_model=Page[CheckpointAsItem])
def list_project_checkpoints(
    project_uuid: ProjectID,
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


@router.patch(
    "/{project_uuid}/checkpoints/{ref_id}",
    response_model=Envelope[CheckpointAsBody],
)
def update_project_checkpoint(
    project_uuid: ProjectID, ref_id: RefID, checkpoint: CheckpointInUpdate
):
    ...


@router.post(
    "/{project_uuid}/checkpoints/{ref_id}:checkout",
    response_model=Envelope[CheckpointAsBody],
)
def checkout_checkpoint(
    project_uuid: ProjectID,
    ref_id: RefID,
):
    ...


@router.get(
    "/{project_uuid}/checkpoints/{ref_id}/workbench/view",
    response_model=Envelope[ProjectWorkbenchViewAsBody],
)
def view_project_workbench_at_checkpoint(
    project_uuid: ProjectID,
    ref_id: RefID,
):
    ...
