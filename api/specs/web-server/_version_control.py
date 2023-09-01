# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.rest_pagination import Page, PageQueryParameters
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.version_control.models import (
    CheckpointAnnotations,
    CheckpointApiModel,
    CheckpointNew,
    RefID,
    RepoApiModel,
    WorkbenchViewApiModel,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "repository",
    ],
)


@router.get("/repos/projects", response_model=Page[RepoApiModel])
def list_repos(_query_params: Annotated[PageQueryParameters, Depends()]):
    ...


@router.get(
    "/repos/projects/{project_uuid}/checkpoints",
    response_model=Page[CheckpointApiModel],
)
def list_checkpoints(
    project_uuid: ProjectID, _query_params: Annotated[PageQueryParameters, Depends()]
):
    ...


@router.post(
    "/repos/projects/{project_uuid}/checkpoints",
    response_model=Envelope[CheckpointApiModel],
)
def create_checkpoint(project_uuid: ProjectID, _new: CheckpointNew):
    ...


@router.get(
    "/repos/projects/{project_uuid}/checkpoints/{ref_id}",
    response_model=Envelope[CheckpointApiModel],
)
def get_checkpoint(ref_id: RefID | Literal["HEAD"], project_uuid: ProjectID):
    ...


@router.patch(
    "/repos/projects/{project_uuid}/checkpoints/{ref_id}",
    response_model=Envelope[CheckpointApiModel],
)
def update_checkpoint(
    ref_id: RefID,
    project_uuid: ProjectID,
    _update: CheckpointAnnotations,
):
    """
    Update Checkpoint Annotations
    """


@router.get(
    "/repos/projects/{project_uuid}/checkpoints/{ref_id}/workbench/view",
    response_model=Envelope[WorkbenchViewApiModel],
)
def view_project_workbench(ref_id: RefID, project_uuid: ProjectID):
    ...


@router.post(
    "/repos/projects/{project_uuid}/checkpoints/{ref_id}:checkout",
    response_model=Envelope[CheckpointApiModel],
)
def checkout(ref_id: RefID, project_uuid: ProjectID):
    ...
