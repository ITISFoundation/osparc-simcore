# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from _common import assert_handler_signature_against_model
from fastapi import APIRouter, status
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.projects_nodes import (
    NodeCreate,
    NodeCreated,
    NodeGet,
    NodeGetIdle,
    NodeGetUnknown,
    NodeOutputs,
    NodePatch,
    NodeRetrieve,
    NodeRetrieved,
    ProjectNodeServicesGet,
    ServiceResourcesDict,
)
from models_library.generics import Envelope
from models_library.groups import GroupID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._crud_handlers import ProjectPathParams
from simcore_service_webserver.projects._nodes_handlers import (
    NodePathParams,
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
def create_node(project_id: str, body: NodeCreate):  # noqa: ARG001
    ...


@router.get(
    # issues with this endpoint https://github.com/ITISFoundation/osparc-simcore/issues/5245
    "/projects/{project_id}/nodes/{node_id}",
    response_model=Envelope[NodeGetIdle | NodeGetUnknown | DynamicServiceGet | NodeGet],
)
def get_node(project_id: str, node_id: str):  # noqa: ARG001
    ...


@router.delete(
    "/projects/{project_id}/nodes/{node_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_node(project_id: str, node_id: str):  # noqa: ARG001
    ...


@router.post(
    "/projects/{project_id}/nodes/{node_id}:retrieve",
    response_model=Envelope[NodeRetrieved],
)
def retrieve_node(
    project_id: str, node_id: str, _retrieve: NodeRetrieve  # noqa: ARG001
): ...


@router.post(
    "/projects/{project_id}/nodes/{node_id}:start",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def start_node(project_id: str, node_id: str):  # noqa: ARG001
    ...


@router.post(
    "/projects/{project_id}/nodes/{node_id}:stop",
    response_model=Envelope[TaskGet],
)
def stop_node(project_id: str, node_id: str):  # noqa: ARG001
    ...


@router.post(
    "/projects/{project_id}/nodes/{node_id}:restart",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def restart_node(project_id: str, node_id: str):  # noqa: ARG001
    """Note that it has only effect on nodes associated to dynamic services"""


@router.patch(
    "/projects/{project_id}/nodes/{node_id}/outputs",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def update_node_outputs(
    project_id: str, node_id: str, _new: NodeOutputs
):  # noqa: ARG001
    ...


@router.patch(
    "/projects/{project_id}/nodes/{node_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
def patch_project_node(
    project_id: ProjectID, node_id: str, _new: NodePatch
):  # noqa: ARG001
    ...


#
# projects/*/nodes/*/resources  COLLECTION -------------------------
#


@router.get(
    "/projects/{project_id}/nodes/{node_id}/resources",
    response_model=Envelope[ServiceResourcesDict],
)
def get_node_resources(project_id: str, node_id: str):  # noqa: ARG001
    ...


@router.put(
    "/projects/{project_id}/nodes/{node_id}/resources",
    response_model=Envelope[ServiceResourcesDict],
)
def replace_node_resources(
    project_id: str, node_id: str, _new: ServiceResourcesDict  # noqa: ARG001
): ...


#
# projects/*/nodes/-/services
#


@router.get(
    "/projects/{project_id}/nodes/-/services",
    response_model=Envelope[ProjectNodeServicesGet],
    # NOTE: will be activated on the follow up from https://github.com/ITISFoundation/osparc-simcore/pull/7287
    include_in_schema=False,
)
async def get_project_services(project_id: ProjectID): ...


@router.get(
    "/projects/{project_id}/nodes/-/services:access",
    response_model=Envelope[_ProjectGroupAccess],
    description="Check whether provided group has access to the project services",
)
async def get_project_services_access_for_gid(
    project_id: ProjectID, for_gid: GroupID  # noqa: ARG001
): ...


assert_handler_signature_against_model(
    get_project_services_access_for_gid, ProjectPathParams
)


#
# projects/*/nodes/-/preview
#


@router.get(
    "/projects/{project_id}/nodes/-/preview",
    response_model=Envelope[list[_ProjectNodePreview]],
    description="Lists all previews in the node's project",
)
async def list_project_nodes_previews(project_id: ProjectID):  # noqa: ARG001
    ...


assert_handler_signature_against_model(list_project_nodes_previews, ProjectPathParams)


@router.get(
    "/projects/{project_id}/nodes/{node_id}/preview",
    response_model=Envelope[_ProjectNodePreview],
    description="Gets a give node's preview",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Node has no preview"}},
)
async def get_project_node_preview(
    project_id: ProjectID, node_id: NodeID  # noqa: ARG001
): ...


assert_handler_signature_against_model(get_project_node_preview, NodePathParams)
