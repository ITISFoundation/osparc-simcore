""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from _common import (
    CURRENT_DIR,
    assert_handler_signature_against_model,
    create_openapi_specs,
)
from fastapi import APIRouter, FastAPI, status
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import GroupID
from simcore_service_webserver.projects._crud_handlers import ProjectPathParams
from simcore_service_webserver.projects._nodes_handlers import (
    _NodePathParams,
    _ProjectGroupAccess,
    _ProjectNodePreview,
)

router = APIRouter(
    tags=[
        "project",
    ]
)


#
# API entrypoints
#


@router.get(
    "/projects/{project_id}/nodes/-/services:access",
    response_model=Envelope[_ProjectGroupAccess],
    operation_id="get_project_services_access_for_gid",
    summary="Check whether provided group has access to the project services",
)
async def get_project_services_access_for_gid(project_id: ProjectID, for_gid: GroupID):
    ...


assert_handler_signature_against_model(
    get_project_services_access_for_gid, ProjectPathParams
)


@router.get(
    "/projects/{project_id}/nodes/-/preview",
    response_model=Envelope[list[_ProjectNodePreview]],
    operation_id="list_project_nodes_previews",
    summary="Lists all previews in the node's project",
)
async def list_project_nodes_previews(project_id: ProjectID):
    ...


assert_handler_signature_against_model(list_project_nodes_previews, ProjectPathParams)


@router.get(
    "/projects/{project_id}/nodes/{node_id}/preview",
    response_model=Envelope[_ProjectNodePreview],
    operation_id="get_project_node_preview",
    summary="Gets a give node's preview",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Node has no preview"}},
)
async def get_project_node_preview(project_id: ProjectID, node_id: NodeID):
    ...


assert_handler_signature_against_model(get_project_node_preview, _NodePathParams)


if __name__ == "__main__":
    create_openapi_specs(
        FastAPI(routes=router.routes),
        CURRENT_DIR.parent / "openapi-projects-nodes.yaml",
    )
