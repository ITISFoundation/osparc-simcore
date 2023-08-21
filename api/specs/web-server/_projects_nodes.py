# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from _common import assert_handler_signature_against_model
from fastapi import APIRouter, status
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.projects_nodes import (
    NodeCreate,
    NodeCreated,
    NodeGet,
    NodeGetIdle,
    NodeRetrieve,
    NodeRetrieved,
    ServiceResourcesDict,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import GroupID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._crud_handlers import ProjectPathParams
from simcore_service_webserver.projects._nodes_handlers import (
    _NodePathParams,
    _ProjectGroupAccess,
    _ProjectNodePreview,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
        "nodes",
    ],
)

# projects/*/nodes COLLECTION -------------------------


@router.post(
    "/projects/{project_id}/nodes",
    response_model=Envelope[NodeCreated],
    status_code=status.HTTP_201_CREATED,
)
def create_node(project_id: str, body: NodeCreate):
    ...


@router.get(
    "/projects/{project_id}/nodes/{node_id}",
    response_model=Envelope[NodeGet | NodeGetIdle],
    # responses={"idle": {"model": NodeGetIdle}}, TODO: check this variant
)
def get_node(
    project_id: str,
    node_id: str,
):
    pass


@router.delete(
    "/projects/{project_id}/nodes/{node_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_node(project_id: str, node_id: str):
    pass


@router.post(
    "/projects/{project_id}/nodes/{node_id}:retrieve",
    response_model=Envelope[NodeRetrieved],
)
def retrieve_node(project_id: str, node_id: str, _retrieve: NodeRetrieve):
    ...


@router.post(
    "/projects/{project_id}/nodes/{node_id}:start",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def start_node(project_id: str, node_id: str):
    ...


@router.post(
    "/projects/{project_id}/nodes/{node_id}:stop",
    response_model=Envelope[TaskGet],
)
def stop_node(project_id: str, node_id: str):
    ...


@router.post(
    "/projects/{project_id}/nodes/{node_id}:restart",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def restart_node(project_id: str, node_id: str):
    """Note that it has only effect on nodes associated to dynamic services"""


#
# projects/*/nodes/*/resources  COLLECTION -------------------------
#


@router.get(
    "/projects/{project_id}/nodes/{node_id}/resources",
    response_model=Envelope[ServiceResourcesDict],
)
def get_node_resources(project_id: str, node_id: str):
    pass


@router.put(
    "/projects/{project_id}/nodes/{node_id}/resources",
    response_model=Envelope[ServiceResourcesDict],
)
def replace_node_resources(project_id: str, node_id: str, _new: ServiceResourcesDict):
    pass


#
# projects/*/nodes/-/services
#


@router.get(
    "/projects/{project_id}/nodes/-/services:access",
    response_model=Envelope[_ProjectGroupAccess],
    summary="Check whether provided group has access to the project services",
)
async def get_project_services_access_for_gid(project_id: ProjectID, for_gid: GroupID):
    ...


assert_handler_signature_against_model(
    get_project_services_access_for_gid, ProjectPathParams
)


#
# projects/*/nodes/-/preview
#


@router.get(
    "/projects/{project_id}/nodes/-/preview",
    response_model=Envelope[list[_ProjectNodePreview]],
    summary="Lists all previews in the node's project",
)
async def list_project_nodes_previews(project_id: ProjectID):
    ...


assert_handler_signature_against_model(list_project_nodes_previews, ProjectPathParams)


@router.get(
    "/projects/{project_id}/nodes/{node_id}/preview",
    response_model=Envelope[_ProjectNodePreview],
    summary="Gets a give node's preview",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Node has no preview"}},
)
async def get_project_node_preview(project_id: ProjectID, node_id: NodeID):
    ...


assert_handler_signature_against_model(get_project_node_preview, _NodePathParams)
