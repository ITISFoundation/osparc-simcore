# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._ports_handlers import (
    ProjectInputGet,
    ProjectInputUpdate,
    ProjectMetadataPortGet,
    ProjectOutputGet,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
        "ports",
    ],
)


@router.get(
    "/projects/{project_id}/inputs",
    response_model=Envelope[dict[NodeID, ProjectInputGet]],
)
async def get_project_inputs(project_id: ProjectID):
    """New in version *0.10*"""


@router.patch(
    "/projects/{project_id}/inputs",
    response_model=Envelope[dict[NodeID, ProjectInputGet]],
)
async def update_project_inputs(
    project_id: ProjectID, _updates: list[ProjectInputUpdate]
):
    """New in version *0.10*"""


@router.get(
    "/projects/{project_id}/outputs",
    response_model=Envelope[dict[NodeID, ProjectOutputGet]],
)
async def get_project_outputs(project_id: ProjectID):
    """New in version *0.10*"""


@router.get(
    "/projects/{project_id}/metadata/ports",
    response_model=Envelope[list[ProjectMetadataPortGet]],
)
async def list_project_metadata_ports(project_id: ProjectID):
    """New in version *0.12*"""
