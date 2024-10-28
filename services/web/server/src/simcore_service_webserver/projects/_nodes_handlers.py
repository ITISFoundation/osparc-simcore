""" Handlers for CRUD operations on /projects/{*}/nodes/{*}

"""

import asyncio
import functools
import logging

from aiohttp import web
from common_library.json_serialization import json_dumps
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
)
from models_library.groups import EVERYONE_GROUP_ID, Group, GroupTypeInModel
from models_library.projects import Project, ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.services import ServiceKeyVersion
from models_library.services_resources import ServiceResourcesDict
from models_library.users import GroupID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, Field
from servicelib.aiohttp import status
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
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rabbitmq import RPCServerError
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)
from servicelib.services_utils import get_status_as_dict
from simcore_postgres_database.models.users import UserRole

from .._meta import API_VTAG as VTAG
from ..catalog import client as catalog_client
from ..director_v2 import api as director_v2_api
from ..dynamic_scheduler import api as dynamic_scheduler_api
from ..groups.api import get_group_from_gid, list_all_user_groups
from ..groups.exceptions import GroupNotFoundError
from ..login.decorators import login_required
from ..projects.api import has_user_project_access_rights
from ..resource_usage.errors import DefaultPricingPlanNotFoundError
from ..security.decorators import permission_required
from ..users.api import get_user_id_from_gid, get_user_role
from ..users.exceptions import UserDefaultWalletNotFoundError
from ..utils_aiohttp import envelope_json_response
from ..wallets.errors import WalletAccessForbiddenError, WalletNotEnoughCreditsError
from . import nodes_utils, projects_api
from ._common_models import ProjectPathParams, RequestContext
from ._nodes_api import NodeScreenshot, get_node_screenshots
from .exceptions import (
    ClustersKeeperNotAvailableError,
    DefaultPricingUnitNotFoundError,
    NodeNotFoundError,
    ProjectInvalidRightsError,
    ProjectNodeRequiredInputsNotSetError,
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
            DefaultPricingPlanNotFoundError,
            DefaultPricingUnitNotFoundError,
            GroupNotFoundError,
            CatalogItemNotFoundError,
        ) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc
        except WalletNotEnoughCreditsError as exc:
            raise web.HTTPPaymentRequired(reason=f"{exc}") from exc
        except ProjectInvalidRightsError as exc:
            raise web.HTTPUnauthorized(reason=f"{exc}") from exc
        except ProjectStartsTooManyDynamicNodesError as exc:
            raise web.HTTPConflict(reason=f"{exc}") from exc
        except ClustersKeeperNotAvailableError as exc:
            raise web.HTTPServiceUnavailable(reason=f"{exc}") from exc
        except ProjectNodeRequiredInputsNotSetError as exc:
            raise web.HTTPConflict(reason=f"{exc}") from exc
        except CatalogForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc
        except WalletAccessForbiddenError as exc:
            raise web.HTTPForbidden(
                reason=f"Payment required, but the user lacks access to the project's linked wallet.: {exc}"
            ) from exc

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
    req_ctx = RequestContext.model_validate(request)
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
    assert NodeCreated.model_validate(data) is not None  # nosec

    return envelope_json_response(data, status_cls=web.HTTPCreated)


@routes.get(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="get_node")
@login_required
@permission_required("project.node.read")
@_handle_project_nodes_exceptions
# NOTE: Careful, this endpoint is actually "get_node_state," and it doesn't return a Node resource.
async def get_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
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

    return envelope_json_response(get_status_as_dict(service_data))


@routes.patch(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="patch_project_node"
)
@login_required
@permission_required("project.node.update")
@_handle_project_nodes_exceptions
async def patch_project_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    node_patch = await parse_request_body_as(NodePatch, request)

    await projects_api.patch_project_node(
        request.app,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        node_id=path_params.node_id,
        node_patch=node_patch,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.delete(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="delete_node")
@login_required
@permission_required("project.node.delete")
@_handle_project_nodes_exceptions
async def delete_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
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
        req_ctx.product_name,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:retrieve",
    name="retrieve_node",
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


@routes.patch(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/outputs",
    name="update_node_outputs",
)
@login_required
@permission_required("project.node.update")
@_handle_project_nodes_exceptions
async def update_node_outputs(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    node_outputs = await parse_request_body_as(NodeOutputs, request)

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
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:start",
    name="start_node",
)
@login_required
@permission_required("project.update")
@_handle_project_nodes_exceptions
async def start_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    await projects_api.start_project_node(
        request,
        product_name=req_ctx.product_name,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        node_id=path_params.node_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


async def _stop_dynamic_service_task(
    _task_progress: TaskProgress,
    *,
    app: web.Application,
    dynamic_service_stop: DynamicServiceStop,
):
    # NOTE: _handle_project_nodes_exceptions only decorate handlers
    try:
        await dynamic_scheduler_api.stop_dynamic_service(
            app, dynamic_service_stop=dynamic_service_stop
        )
        return web.json_response(status=status.HTTP_204_NO_CONTENT)

    except (RPCServerError, ServiceWaitingForManualInterventionError) as exc:
        # in case there is an error reply as not found
        raise web.HTTPNotFound(reason=f"{exc}") from exc

    except ServiceWasNotFoundError:
        # in case the service is not found reply as all OK
        return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:stop", name="stop_node"
)
@login_required
@permission_required("project.update")
@_handle_project_nodes_exceptions
async def stop_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    save_state = await has_user_project_access_rights(
        request.app,
        project_id=path_params.project_id,
        user_id=req_ctx.user_id,
        permission="write",
    )

    user_role = await get_user_role(request.app, req_ctx.user_id)
    if user_role is None or user_role <= UserRole.GUEST:
        save_state = False

    return await start_long_running_task(
        request,
        _stop_dynamic_service_task,  # type: ignore[arg-type] # @GitHK, @pcrespov this one I don't know how to fix
        task_context=jsonable_encoder(req_ctx),
        # task arguments from here on ---
        app=request.app,
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
@_handle_project_nodes_exceptions
async def restart_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""

    path_params = parse_request_path_parameters_as(NodePathParams, request)

    await director_v2_api.restart_dynamic_service(request.app, f"{path_params.node_id}")

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
@_handle_project_nodes_exceptions
async def get_node_resources(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
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
    req_ctx = RequestContext.model_validate(request)
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
async def get_project_services_access_for_gid(
    request: web.Request,
) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    query_params: _ServicesAccessQuery = parse_request_query_parameters_as(
        _ServicesAccessQuery, request
    )

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

    # Initialize groups to compare with everyone group ID
    groups_to_compare = {EVERYONE_GROUP_ID}

    # Get the group from the provided group ID
    _sharing_with_group: Group | None = await get_group_from_gid(
        app=request.app, gid=query_params.for_gid
    )

    # Check if the group exists
    if _sharing_with_group is None:
        raise GroupNotFoundError(gid=query_params.for_gid)

    # Update groups to compare based on the type of sharing group
    if _sharing_with_group.group_type == GroupTypeInModel.PRIMARY:
        _user_id = await get_user_id_from_gid(
            app=request.app, primary_gid=query_params.for_gid
        )
        _user_groups = await list_all_user_groups(app=request.app, user_id=_user_id)
        groups_to_compare.update({group.gid for group in _user_groups})
        groups_to_compare.add(query_params.for_gid)
    elif _sharing_with_group.group_type == GroupTypeInModel.STANDARD:
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
@_handle_project_nodes_exceptions
async def list_project_nodes_previews(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    assert req_ctx  # nosec

    nodes_previews: list[_ProjectNodePreview] = []
    project_data = await projects_api.get_project_for_user(
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
@_handle_project_nodes_exceptions
async def get_project_node_preview(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)
    assert req_ctx  # nosec

    project_data = await projects_api.get_project_for_user(
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
