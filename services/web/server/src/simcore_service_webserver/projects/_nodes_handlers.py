""" Handlers for CRUD operations on /projects/{*}/nodes/{*}

"""

import asyncio
import functools
import logging

from aiohttp import web
from models_library.api_schemas_catalog.service_access_rights import (
    ServiceAccessRightsGet,
)
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import (
    NodeCreate,
    NodeCreated,
    NodeGet,
    NodeGetIdle,
    NodeGetUnknown,
    NodeRetrieve,
)
from models_library.groups import EVERYONE_GROUP_ID
from models_library.projects import Project, ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import NodeIDStr
from models_library.services import ServiceKeyVersion
from models_library.services_resources import ServiceResourcesDict
from models_library.users import GroupID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, Field, parse_obj_as
from servicelib.aiohttp.long_running_tasks.server import (
    TaskProgress,
    start_long_running_task,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rabbitmq import RPCServerError
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)
from simcore_postgres_database.models.users import UserRole

from .._meta import API_VTAG as VTAG
from ..catalog import client as catalog_client
from ..director_v2 import api as director_v2_api
from ..dynamic_scheduler import api as dynamic_scheduler_api
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..users.api import get_user_role
from ..users.exceptions import UserDefaultWalletNotFoundError
from ..utils_aiohttp import envelope_json_response
from ..wallets.errors import WalletNotEnoughCreditsError
from . import projects_api
from ._common_models import ProjectPathParams, RequestContext
from ._nodes_api import NodeScreenshot, get_node_screenshots
from .db import ProjectDBAPI
from .exceptions import (
    DefaultPricingUnitNotFoundError,
    NodeNotFoundError,
    ProjectNodeResourcesInsufficientRightsError,
    ProjectNodeResourcesInvalidError,
    ProjectNotFoundError,
    ProjectStartsTooManyDynamicNodesError,
)

_logger = logging.getLogger(__name__)


def _handle_project_nodes_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (
            ProjectNotFoundError,
            NodeNotFoundError,
            UserDefaultWalletNotFoundError,
            DefaultPricingUnitNotFoundError,
        ) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc
        except WalletNotEnoughCreditsError as exc:
            raise web.HTTPPaymentRequired(reason=f"{exc}") from exc

    return wrapper


#
# projects/*/nodes COLLECTION -------------------------
#

routes = web.RouteTableDef()


class NodePathParams(ProjectPathParams):
    node_id: NodeID


@routes.post(f"/{VTAG}/projects/{{project_id}}/nodes", name="create_node")
@login_required
@permission_required("project.node.create")
@_handle_project_nodes_exceptions
async def create_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    body = await parse_request_body_as(NodeCreate, request)

    if await projects_api.is_service_deprecated(
        request.app,
        req_ctx.user_id,
        body.service_key,
        body.service_version,
        req_ctx.product_name,
    ):
        raise web.HTTPNotAcceptable(
            reason=f"Service {body.service_key}:{body.service_version} is deprecated"
        )

    # ensure the project exists
    project_data = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    data = {
        "node_id": await projects_api.add_project_node(
            request,
            project_data,
            req_ctx.user_id,
            req_ctx.product_name,
            body.service_key,
            body.service_version,
            body.service_id,
        )
    }
    assert parse_obj_as(NodeCreated, data) is not None  # nosec

    return envelope_json_response(data, status_cls=web.HTTPCreated)


@routes.get(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="get_node")
@login_required
@permission_required("project.node.read")
@_handle_project_nodes_exceptions
async def get_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    # ensure the project exists
    project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )

    if await projects_api.is_project_node_deprecated(
        request.app,
        req_ctx.user_id,
        project,
        path_params.node_id,
        req_ctx.product_name,
    ):
        project_node = project["workbench"][f"{path_params.node_id}"]
        raise web.HTTPNotAcceptable(
            reason=f"Service {project_node['key']}:{project_node['version']} is deprecated!"
        )

    service_data: NodeGetIdle | NodeGetUnknown | DynamicServiceGet | NodeGet = (
        await dynamic_scheduler_api.get_dynamic_service(
            app=request.app, node_id=path_params.node_id
        )
    )

    return envelope_json_response(
        service_data.dict(by_alias=True)
        if isinstance(service_data, DynamicServiceGet)
        else service_data.dict()
    )


@routes.delete(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="delete_node")
@login_required
@permission_required("project.node.delete")
@_handle_project_nodes_exceptions
async def delete_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    await projects_api.delete_project_node(
        request,
        path_params.project_id,
        req_ctx.user_id,
        NodeIDStr(path_params.node_id),
    )

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:retrieve", name="retrieve_node"
)
@login_required
@permission_required("project.node.read")
@_handle_project_nodes_exceptions
async def retrieve_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    retrieve = await parse_request_body_as(NodeRetrieve, request)

    return web.json_response(
        await director_v2_api.retrieve(
            request.app, f"{path_params.node_id}", retrieve.port_keys
        ),
        dumps=json_dumps,
    )


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:start", name="start_node"
)
@login_required
@permission_required("project.update")
@_handle_project_nodes_exceptions
async def start_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    try:
        await projects_api.start_project_node(
            request,
            product_name=req_ctx.product_name,
            user_id=req_ctx.user_id,
            project_id=path_params.project_id,
            node_id=path_params.node_id,
        )

        raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)

    except ProjectStartsTooManyDynamicNodesError as exc:
        raise web.HTTPConflict(reason=f"{exc}") from exc


async def _stop_dynamic_service_task(
    _task_progress: TaskProgress,
    *,
    app: web.Application,
    node_id: NodeID,
    simcore_user_agent: str,
    save_state: bool,
):
    # NOTE: _handle_project_nodes_exceptions only decorate handlers
    try:
        await dynamic_scheduler_api.stop_dynamic_service(
            app,
            node_id=node_id,
            simcore_user_agent=simcore_user_agent,
            save_state=save_state,
        )
        raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)

    # in case there is an error reply as not found
    except (RPCServerError, ServiceWaitingForManualInterventionError) as exc:
        raise web.HTTPNotFound(reason=f"{exc}") from exc

    # in case the service is not found reply as all OK
    except ServiceWasNotFoundError as exc:
        raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON) from exc


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:stop", name="stop_node"
)
@login_required
@permission_required("project.update")
@_handle_project_nodes_exceptions
async def stop_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    save_state = await ProjectDBAPI.get_from_app_context(request.app).has_permission(
        user_id=req_ctx.user_id,
        project_uuid=f"{path_params.project_id}",
        permission="write",
    )

    user_role = await get_user_role(request.app, req_ctx.user_id)
    if user_role is None or user_role <= UserRole.GUEST:
        save_state = False

    return await start_long_running_task(
        request,
        _stop_dynamic_service_task,
        task_context=jsonable_encoder(req_ctx),
        # task arguments from here on ---
        app=request.app,
        node_id=path_params.node_id,
        simcore_user_agent=request.headers.get(
            X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
        ),
        save_state=save_state,
        fire_and_forget=True,
    )


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:restart", name="restart_node"
)
@login_required
@permission_required("project.node.read")
@_handle_project_nodes_exceptions
async def restart_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""

    path_params = parse_request_path_parameters_as(NodePathParams, request)

    await director_v2_api.restart_dynamic_service(request.app, f"{path_params.node_id}")

    raise web.HTTPNoContent


#
# projects/*/nodes/*/resources  COLLECTION -------------------------
#


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/resources",
    name="get_node_resources",
)
@login_required
@permission_required("project.node.read")
@_handle_project_nodes_exceptions
async def get_node_resources(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    # ensure the project exists
    project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    if f"{path_params.node_id}" not in project["workbench"]:
        project_uuid = f"{path_params.project_id}"
        node_id = f"{path_params.node_id}"
        raise NodeNotFoundError(project_uuid=project_uuid, node_uuid=node_id)

    resources: ServiceResourcesDict = await projects_api.get_project_node_resources(
        request.app,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        node_id=path_params.node_id,
        service_key=project["workbench"][f"{path_params.node_id}"]["key"],
        service_version=project["workbench"][f"{path_params.node_id}"]["version"],
    )
    return envelope_json_response(resources)


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/resources",
    name="replace_node_resources",
)
@login_required
@permission_required("project.node.update")
@_handle_project_nodes_exceptions
async def replace_node_resources(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    body = await parse_request_body_as(ServiceResourcesDict, request)

    # ensure the project exists
    project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    if f"{path_params.node_id}" not in project["workbench"]:
        raise NodeNotFoundError(
            project_uuid=f"{path_params.project_id}", node_uuid=f"{path_params.node_id}"
        )
    try:
        new_node_resources = await projects_api.update_project_node_resources(
            request.app,
            user_id=req_ctx.user_id,
            project_id=path_params.project_id,
            node_id=path_params.node_id,
            service_key=project["workbench"][f"{path_params.node_id}"]["key"],
            service_version=project["workbench"][f"{path_params.node_id}"]["version"],
            product_name=req_ctx.product_name,
            resources=body,
        )

        return envelope_json_response(new_node_resources)
    except ProjectNodeResourcesInvalidError as exc:
        raise web.HTTPUnprocessableEntity(  # 422
            reason=f"{exc}",
            text=f"{exc}",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from exc
    except ProjectNodeResourcesInsufficientRightsError as exc:
        raise web.HTTPForbidden(
            reason=f"{exc}",
            text=f"{exc}",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from exc


class _ServicesAccessQuery(BaseModel):
    for_gid: GroupID


class _ProjectGroupAccess(BaseModel):
    gid: GroupID
    accessible: bool
    inaccessible_services: list[ServiceKeyVersion] | None = Field(default=None)


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/nodes/-/services:access",
    name="get_project_services_access_for_gid",
)
@login_required
@permission_required("project.read")
@_handle_project_nodes_exceptions
async def get_project_services_access_for_gid(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    query_params = parse_request_query_parameters_as(_ServicesAccessQuery, request)

    project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=True,
    )
    project_services: list[ServiceKeyVersion] = [
        ServiceKeyVersion(key=s["key"], version=s["version"])
        for _, s in project["workbench"].items()
    ]

    project_services_access_rights: list[ServiceAccessRightsGet] = await asyncio.gather(
        *[
            catalog_client.get_service_access_rights(
                app=request.app,
                user_id=req_ctx.user_id,
                service_key=service.key,
                service_version=service.version,
                product_name=req_ctx.product_name,
            )
            for service in project_services
        ]
    )

    inaccessible_services = []
    for service in project_services_access_rights:
        service_access_rights = service.gids_with_access_rights

        # Ignore services shared with everyone
        if service_access_rights.get(EVERYONE_GROUP_ID):
            continue

        # Check if service is accessible to the provided group
        service_access_rights_for_gid = service_access_rights.get(
            query_params.for_gid, {}
        )

        if (
            not service_access_rights_for_gid
            or service_access_rights_for_gid.get("execute_access", False) is False
        ):
            inaccessible_services.append(service)

    project_accessible = not inaccessible_services
    project_inaccessible_services = (
        [
            ServiceKeyVersion(
                key=s.service_key,
                version=s.service_version,
            )
            for s in inaccessible_services
        ]
        if inaccessible_services
        else None
    )

    project_group_access = _ProjectGroupAccess(
        gid=query_params.for_gid,
        accessible=project_accessible,
        inaccessible_services=project_inaccessible_services,
    )

    return envelope_json_response(project_group_access.dict(exclude_none=True))


class _ProjectNodePreview(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    screenshots: list[NodeScreenshot] = Field(default_factory=list)


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/nodes/-/preview",
    name="list_project_nodes_previews",
)
@login_required
@permission_required("project.read")
@_handle_project_nodes_exceptions
async def list_project_nodes_previews(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    assert req_ctx  # nosec

    nodes_previews: list[_ProjectNodePreview] = []
    project_data = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    project = Project.parse_obj(project_data)

    for node_id, node in project.workbench.items():
        screenshots = await get_node_screenshots(
            app=request.app,
            user_id=req_ctx.user_id,
            project_id=path_params.project_id,
            node_id=NodeID(node_id),
            node=node,
        )
        if screenshots:
            nodes_previews.append(
                _ProjectNodePreview(
                    project_id=path_params.project_id,
                    node_id=NodeID(node_id),
                    screenshots=screenshots,
                )
            )

    return envelope_json_response(nodes_previews)


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/preview",
    name="get_project_node_preview",
)
@login_required
@permission_required("project.read")
@_handle_project_nodes_exceptions
async def get_project_node_preview(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    assert req_ctx  # nosec

    project_data = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )

    project = Project.parse_obj(project_data)

    node = project.workbench.get(NodeIDStr(path_params.node_id))
    if node is None:
        raise NodeNotFoundError(
            project_uuid=f"{path_params.project_id}",
            node_uuid=f"{path_params.node_id}",
        )

    node_preview = _ProjectNodePreview(
        project_id=project.uuid,
        node_id=path_params.node_id,
        screenshots=await get_node_screenshots(
            app=request.app,
            user_id=req_ctx.user_id,
            project_id=path_params.project_id,
            node_id=path_params.node_id,
            node=node,
        ),
    )
    return envelope_json_response(node_preview)
