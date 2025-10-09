import asyncio
import logging

from aiohttp import web
from common_library.error_codes import create_error_code
from common_library.json_serialization import json_dumps
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from common_library.user_messages import user_message
from models_library.api_schemas_catalog.service_access_rights import (
    ServiceAccessRightsGet,
)
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import (
    NodeCreate,
    NodeCreated,
    NodeGet,
    NodeGetIdle,
    NodeGetUnknown,
    NodeOutputs,
    NodePatch,
    NodeRetrieve,
    NodeServiceGet,
    ProjectNodeServicesGet,
)
from models_library.basic_types import IDStr
from models_library.groups import EVERYONE_GROUP_ID, Group, GroupID, GroupType
from models_library.projects import Project, ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.rest_error import ErrorGet
from models_library.services import ServiceKeyVersion
from models_library.services_resources import ServiceResourcesDict
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, Field
from servicelib.aiohttp import status
from servicelib.aiohttp.long_running_tasks.server import start_long_running_task
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_headers_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from servicelib.long_running_tasks.models import TaskProgress
from servicelib.long_running_tasks.task import TaskRegistry
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rabbitmq import RPCServerError
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)
from servicelib.services_utils import get_status_as_dict
from simcore_postgres_database.models.users import UserRole

from ..._meta import API_VTAG as VTAG
from ...catalog import catalog_service
from ...dynamic_scheduler import api as dynamic_scheduler_service
from ...exception_handling import create_error_response
from ...groups import api as groups_service
from ...groups.exceptions import GroupNotFoundError
from ...login.decorators import login_required
from ...models import ClientSessionHeaderParams
from ...security.decorators import permission_required
from ...users import users_service
from ...utils_aiohttp import envelope_json_response, get_api_base_url
from .. import _access_rights_service as access_rights_service
from .. import _nodes_service, _projects_service, nodes_utils
from .._nodes_service import NodeScreenshot, get_node_screenshots
from ..api import has_user_project_access_rights
from ..exceptions import (
    NodeNotFoundError,
    ProjectNodeResourcesInsufficientRightsError,
    ProjectNodeResourcesInvalidError,
)
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import AuthenticatedRequestContext, ProjectPathParams

_logger = logging.getLogger(__name__)


#
# projects/*/nodes COLLECTION -------------------------
#

routes = web.RouteTableDef()


class NodePathParams(ProjectPathParams):
    node_id: NodeID


@routes.post(f"/{VTAG}/projects/{{project_id}}/nodes", name="create_node")
@login_required
@permission_required("project.node.create")
@handle_plugin_requests_exceptions
async def create_node(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    body = await parse_request_body_as(NodeCreate, request)
    header_params = parse_request_headers_as(ClientSessionHeaderParams, request)

    if await _projects_service.is_service_deprecated(
        request.app,
        req_ctx.user_id,
        body.service_key,
        body.service_version,
        req_ctx.product_name,
    ):
        raise web.HTTPNotAcceptable(
            text=f"Service {body.service_key}:{body.service_version} is deprecated"
        )

    # ensure the project exists
    project_data = await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    data = {
        "node_id": await _projects_service.add_project_node(
            request,
            project_data,
            req_ctx.user_id,
            req_ctx.product_name,
            get_api_base_url(request),
            body.service_key,
            body.service_version,
            body.service_id,
            client_session_id=header_params.client_session_id,
        )
    }
    assert NodeCreated.model_validate(data) is not None  # nosec

    return envelope_json_response(data, status_cls=web.HTTPCreated)


@routes.get(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="get_node")
@login_required
@permission_required("project.node.read")
@handle_plugin_requests_exceptions
# NOTE: Careful, this endpoint is actually "get_node_state," and it doesn't return a Node resource.
async def get_node(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    # ensure the project exists
    project = await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )

    if await _projects_service.is_project_node_deprecated(
        request.app,
        req_ctx.user_id,
        project,
        path_params.node_id,
        req_ctx.product_name,
    ):
        project_node = project["workbench"][f"{path_params.node_id}"]
        raise web.HTTPNotAcceptable(
            text=f"Service {project_node['key']}:{project_node['version']} is deprecated!"
        )

    service_data: NodeGetIdle | NodeGetUnknown | DynamicServiceGet | NodeGet = (
        await dynamic_scheduler_service.get_dynamic_service(
            app=request.app, node_id=path_params.node_id
        )
    )

    return envelope_json_response(get_status_as_dict(service_data))


@routes.patch(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="patch_project_node"
)
@login_required
@permission_required("project.node.update")
@handle_plugin_requests_exceptions
async def patch_project_node(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    node_patch = await parse_request_body_as(NodePatch, request)
    header_params = parse_request_headers_as(ClientSessionHeaderParams, request)

    await _projects_service.patch_project_node(
        request.app,
        product_name=req_ctx.product_name,
        product_api_base_url=get_api_base_url(request),
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        node_id=path_params.node_id,
        partial_node=node_patch.to_domain_model(),
        client_session_id=header_params.client_session_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.delete(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="delete_node")
@login_required
@permission_required("project.node.delete")
@handle_plugin_requests_exceptions
async def delete_node(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    header_params = parse_request_headers_as(ClientSessionHeaderParams, request)

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    await _projects_service.delete_project_node(
        request,
        path_params.project_id,
        req_ctx.user_id,
        f"{path_params.node_id}",
        req_ctx.product_name,
        product_api_base_url=get_api_base_url(request),
        client_session_id=header_params.client_session_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:retrieve",
    name="retrieve_node",
)
@login_required
@permission_required("project.node.read")
@handle_plugin_requests_exceptions
async def retrieve_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    retrieve = await parse_request_body_as(NodeRetrieve, request)

    return web.json_response(
        await dynamic_scheduler_service.retrieve_inputs(
            request.app, path_params.node_id, retrieve.port_keys
        ),
        dumps=json_dumps,
    )


@routes.patch(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/outputs",
    name="update_node_outputs",
)
@login_required
@permission_required("project.node.update")
@handle_plugin_requests_exceptions
async def update_node_outputs(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    node_outputs = await parse_request_body_as(NodeOutputs, request)
    header_params = parse_request_headers_as(ClientSessionHeaderParams, request)

    ui_changed_keys = set()
    ui_changed_keys.add(f"{path_params.node_id}")
    await nodes_utils.update_node_outputs(
        app=request.app,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        node_uuid=path_params.node_id,
        outputs=node_outputs.outputs,
        run_hash=None,
        node_errors=None,
        ui_changed_keys=ui_changed_keys,
        client_session_id=header_params.client_session_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:start",
    name="start_node",
)
@login_required
@permission_required("project.update")
@handle_plugin_requests_exceptions
async def start_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    await _projects_service.start_project_node(
        request,
        product_name=req_ctx.product_name,
        product_api_base_url=get_api_base_url(request),
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        node_id=path_params.node_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


async def _stop_dynamic_service_task(
    progress: TaskProgress,
    *,
    app: web.Application,
    dynamic_service_stop: DynamicServiceStop,
) -> web.Response:
    _ = progress
    # NOTE: _handle_project_nodes_exceptions only decorate handlers
    try:
        await dynamic_scheduler_service.stop_dynamic_service(
            app, dynamic_service_stop=dynamic_service_stop
        )
        project = await _projects_service.get_project_for_user(
            app,
            f"{dynamic_service_stop.project_id}",
            dynamic_service_stop.user_id,
            include_state=True,
        )
        await _projects_service.notify_project_node_update(
            app, project, dynamic_service_stop.node_id, errors=None
        )
        return web.json_response(status=status.HTTP_204_NO_CONTENT)

    except (RPCServerError, ServiceWaitingForManualInterventionError) as exc:
        error_code = getattr(exc, "error_code", None) or create_error_code(exc)
        user_error_msg = user_message(
            f"Could not stop dynamic service {dynamic_service_stop.project_id}.{dynamic_service_stop.node_id}"
        )
        _logger.debug(
            **create_troubleshooting_log_kwargs(
                user_error_msg,
                error=exc,
                error_code=error_code,
                error_context={
                    "project_id": dynamic_service_stop.project_id,
                    "node_id": dynamic_service_stop.node_id,
                    "user_id": dynamic_service_stop.user_id,
                    "save_state": dynamic_service_stop.save_state,
                    "simcore_user_agent": dynamic_service_stop.simcore_user_agent,
                },
            )
        )
        # ANE: in case there is an error reply as not found
        return create_error_response(
            error=ErrorGet(
                message=user_error_msg,
                support_id=IDStr(error_code),
                status=status.HTTP_404_NOT_FOUND,
            ),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    except ServiceWasNotFoundError:
        # in case the service is not found reply as all OK
        return web.json_response(status=status.HTTP_204_NO_CONTENT)


def register_stop_dynamic_service_task(app: web.Application) -> None:
    TaskRegistry.register(_stop_dynamic_service_task, app=app)


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:stop", name="stop_node"
)
@login_required
@permission_required("project.update")
@handle_plugin_requests_exceptions
async def stop_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    save_state = await has_user_project_access_rights(
        request.app,
        project_id=path_params.project_id,
        user_id=req_ctx.user_id,
        permission="write",
    )

    user_role = await users_service.get_user_role(request.app, user_id=req_ctx.user_id)
    if user_role is None or user_role <= UserRole.GUEST:
        save_state = False

    return await start_long_running_task(
        request,
        _stop_dynamic_service_task.__name__,
        task_context=jsonable_encoder(req_ctx),
        # task arguments from here on ---
        dynamic_service_stop=DynamicServiceStop(
            user_id=req_ctx.user_id,
            project_id=path_params.project_id,
            node_id=path_params.node_id,
            simcore_user_agent=request.headers.get(
                X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
            ),
            save_state=save_state,
        ),
        fire_and_forget=True,
    )


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:restart",
    name="restart_node",
)
@login_required
@permission_required("project.node.read")
@handle_plugin_requests_exceptions
async def restart_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""

    path_params = parse_request_path_parameters_as(NodePathParams, request)

    await dynamic_scheduler_service.restart_user_services(
        request.app, node_id=path_params.node_id
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# projects/*/nodes/*/resources  COLLECTION -------------------------
#


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/resources",
    name="get_node_resources",
)
@login_required
@permission_required("project.node.read")
@handle_plugin_requests_exceptions
async def get_node_resources(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    # ensure the project exists
    project = await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    if f"{path_params.node_id}" not in project["workbench"]:
        project_uuid = f"{path_params.project_id}"
        node_id = f"{path_params.node_id}"
        raise NodeNotFoundError(project_uuid=project_uuid, node_uuid=node_id)

    resources: ServiceResourcesDict = (
        await _projects_service.get_project_node_resources(
            request.app,
            user_id=req_ctx.user_id,
            project_id=path_params.project_id,
            node_id=path_params.node_id,
            service_key=project["workbench"][f"{path_params.node_id}"]["key"],
            service_version=project["workbench"][f"{path_params.node_id}"]["version"],
        )
    )
    return envelope_json_response(resources)


@routes.put(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/resources",
    name="replace_node_resources",
)
@login_required
@permission_required("project.node.update")
@handle_plugin_requests_exceptions
async def replace_node_resources(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    body = await parse_request_body_as(ServiceResourcesDict, request)

    # ensure the project exists
    project = await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    if f"{path_params.node_id}" not in project["workbench"]:
        raise NodeNotFoundError(
            project_uuid=f"{path_params.project_id}", node_uuid=f"{path_params.node_id}"
        )
    try:
        new_node_resources = await _projects_service.update_project_node_resources(
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
            text=f"{exc}",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from exc
    except ProjectNodeResourcesInsufficientRightsError as exc:
        raise web.HTTPForbidden(
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
    f"/{VTAG}/projects/{{project_id}}/nodes/-/services",
    name="get_project_services",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_services(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    await access_rights_service.check_user_project_permission(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        permission="read",
    )

    services_in_project: list[tuple[ServiceKey, ServiceVersion]] = (
        await _nodes_service.get_project_nodes_services(
            request.app, project_uuid=path_params.project_id
        )
    )

    batch_got = await catalog_service.batch_get_my_services(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        services_ids=services_in_project,
    )

    return envelope_json_response(
        ProjectNodeServicesGet(
            project_uuid=path_params.project_id,
            services=[
                NodeServiceGet.model_validate(sv, from_attributes=True)
                for sv in batch_got.found_items
            ],
            missing=(
                [
                    ServiceKeyVersion(key=k, version=v)
                    for k, v in batch_got.missing_identifiers
                ]
                if batch_got.missing_identifiers
                else None
            ),
        )
    )


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/nodes/-/services:access",
    name="get_project_services_access_for_gid",
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_services_access_for_gid(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    query_params: _ServicesAccessQuery = parse_request_query_parameters_as(
        _ServicesAccessQuery, request
    )

    project = await _projects_service.get_project_for_user(
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
            catalog_service.get_service_access_rights(
                app=request.app,
                user_id=req_ctx.user_id,
                service_key=service.key,
                service_version=service.version,
                product_name=req_ctx.product_name,
            )
            for service in project_services
        ]
    )

    # Initialize groups to compare with everyone group ID
    groups_to_compare = {EVERYONE_GROUP_ID}

    # Get the group from the provided group ID
    _sharing_with_group: Group | None = await groups_service.get_group_by_gid(
        app=request.app, group_id=query_params.for_gid
    )

    # Check if the group exists
    if _sharing_with_group is None:
        raise GroupNotFoundError(gid=query_params.for_gid)

    # Update groups to compare based on the type of sharing group
    if _sharing_with_group.group_type == GroupType.PRIMARY:
        _user_id = await users_service.get_user_id_from_gid(
            app=request.app, primary_gid=query_params.for_gid
        )
        user_groups_ids = await groups_service.list_all_user_groups_ids(
            app=request.app, user_id=_user_id
        )
        groups_to_compare.update(set(user_groups_ids))
        groups_to_compare.add(query_params.for_gid)
    elif _sharing_with_group.group_type == GroupType.STANDARD:
        groups_to_compare = {query_params.for_gid}

    # Initialize a list for inaccessible services
    inaccessible_services = []

    # Check accessibility of each service
    for service in project_services_access_rights:
        service_access_rights = service.gids_with_access_rights

        # Find common groups between service access rights and groups to compare
        _groups_intersection = set(service_access_rights.keys()).intersection(
            groups_to_compare
        )

        _is_service_accessible = False

        # Iterate through common groups
        for group in _groups_intersection:
            service_access_rights_for_gid = service_access_rights.get(group)
            assert service_access_rights_for_gid is not None  # nosec
            # Check if execute access is granted for the group
            if service_access_rights_for_gid.get("execute_access", False):
                _is_service_accessible = True
                break

        # If service is not accessible, add it to the list of inaccessible services
        if not _is_service_accessible:
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

    return envelope_json_response(project_group_access.model_dump(exclude_none=True))


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
@handle_plugin_requests_exceptions
async def list_project_nodes_previews(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    assert req_ctx  # nosec

    nodes_previews: list[_ProjectNodePreview] = []
    project_data = await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    project = Project.model_validate(project_data)

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
@handle_plugin_requests_exceptions
async def get_project_node_preview(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    assert req_ctx  # nosec

    project_data = await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )

    project = Project.model_validate(project_data)

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
