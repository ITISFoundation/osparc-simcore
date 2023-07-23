""" Handlers for CRUD operations on /projects/{*}/nodes/{*}

"""

import asyncio
import functools
import logging
from typing import Any

from aiohttp import web
from models_library.api_schemas_catalog.service_access_rights import ServiceAccessRightsGet
from models_library.api_schemas_webserver.projects_nodes import (
    NodeCreate,
    NodeCreated,
    NodeGet,
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
from pydantic import BaseModel, Field
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
from simcore_postgres_database.models.users import UserRole

from .._constants import APP_SETTINGS_KEY, MSG_UNDER_DEVELOPMENT
from .._meta import API_VTAG as VTAG
from ..catalog import client as catalog_client
from ..director_v2 import api
from ..director_v2.exceptions import DirectorServiceError
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..users.api import get_user_role
from ..utils_aiohttp import envelope_json_response
from . import projects_api
from ._common_models import ProjectPathParams, RequestContext
from ._nodes_api import NodeScreenshot, fake_screenshots_factory
from .db import ProjectDBAPI
from .exceptions import (
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

        except (ProjectNotFoundError, NodeNotFoundError) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

    return wrapper


#
# projects/*/nodes COLLECTION -------------------------
#

routes = web.RouteTableDef()


class _NodePathParams(ProjectPathParams):
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
    assert NodeCreated.parse_obj(data)  # nosec

    return envelope_json_response(data, status_cls=web.HTTPCreated)


@routes.get(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="get_node")
@login_required
@permission_required("project.node.read")
@_handle_project_nodes_exceptions
async def get_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_NodePathParams, request)

    try:
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

        # NOTE: for legacy services a redirect to director-v0 is made
        service_data: dict[str, Any] = await api.get_dynamic_service(
            app=request.app, node_uuid=f"{path_params.node_id}"
        )

        if "data" not in service_data:
            # dynamic-service NODE STATE
            assert NodeGet.parse_obj(service_data)  # nosec
            return envelope_json_response(service_data)

        # LEGACY-service NODE STATE
        assert NodeGet.parse_obj(service_data)  # nosec
        return envelope_json_response(service_data["data"])

    except DirectorServiceError as exc:
        if exc.status == web.HTTPNotFound.status_code:
            # the service was not started, so it's state is not started or idle
            return envelope_json_response(
                {
                    "service_state": "idle",
                    "service_uuid": f"{path_params.node_id}",
                }
            )
        raise


@routes.delete(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}", name="delete_node")
@login_required
@permission_required("project.node.delete")
@_handle_project_nodes_exceptions
async def delete_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_NodePathParams, request)

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
    path_params = parse_request_path_parameters_as(_NodePathParams, request)
    retrieve = await parse_request_body_as(NodeRetrieve, request)

    return web.json_response(
        await api.retrieve(request.app, f"{path_params.node_id}", retrieve.port_keys),
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
    path_params = parse_request_path_parameters_as(_NodePathParams, request)
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


async def _stop_dynamic_service_with_progress(
    _task_progress: TaskProgress, *args, **kwargs
):
    # NOTE: _handle_project_nodes_exceptions only decorate handlers
    try:
        await api.stop_dynamic_service(*args, **kwargs)
        raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)

    except (ProjectNotFoundError, NodeNotFoundError) as exc:
        raise web.HTTPNotFound(reason=f"{exc}") from exc
    except DirectorServiceError as exc:
        if exc.status == web.HTTPNotFound.status_code:
            # already stopped, it's all right
            raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON) from exc
        raise


@routes.post(
    f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:stop", name="stop_node"
)
@login_required
@permission_required("project.update")
@_handle_project_nodes_exceptions
async def stop_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_NodePathParams, request)

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
        _stop_dynamic_service_with_progress,
        task_context=jsonable_encoder(req_ctx),
        # task arguments from here on ---
        app=request.app,
        service_uuid=f"{path_params.node_id}",
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

    path_params = parse_request_path_parameters_as(_NodePathParams, request)

    await api.restart_dynamic_service(request.app, f"{path_params.node_id}")

    raise web.HTTPNoContent()


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
    path_params = parse_request_path_parameters_as(_NodePathParams, request)

    # ensure the project exists
    project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    if f"{path_params.node_id}" not in project["workbench"]:
        raise NodeNotFoundError(f"{path_params.project_id}", f"{path_params.node_id}")

    resources = await projects_api.get_project_node_resources(
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
    path_params = parse_request_path_parameters_as(_NodePathParams, request)
    body = await parse_request_body_as(ServiceResourcesDict, request)

    # ensure the project exists
    project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    if f"{path_params.node_id}" not in project["workbench"]:
        raise NodeNotFoundError(f"{path_params.project_id}", f"{path_params.node_id}")
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

    if not request.app[APP_SETTINGS_KEY].WEBSERVER_DEV_FEATURES_ENABLED:
        raise NotImplementedError(MSG_UNDER_DEVELOPMENT)

    nodes_previews: list[_ProjectNodePreview] = []
    project_data = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    project = Project.parse_obj(project_data)

    for node_id, node in project.workbench.items():
        screenshots = await fake_screenshots_factory(request, NodeID(node_id), node)
        if screenshots:
            nodes_previews.append(
                _ProjectNodePreview(
                    project_id=path_params.project_id,
                    node_id=node_id,
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
    path_params = parse_request_path_parameters_as(_NodePathParams, request)
    assert req_ctx  # nosec

    if not request.app[APP_SETTINGS_KEY].WEBSERVER_DEV_FEATURES_ENABLED:
        raise NotImplementedError(MSG_UNDER_DEVELOPMENT)

    project_data = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )

    project = Project.parse_obj(project_data)

    node = project.workbench.get(f"{path_params.node_id}")
    if node is None:
        raise NodeNotFoundError(
            project_uuid=f"{path_params.project_id}",
            node_uuid=f"{path_params.node_id}",
        )

    # NOTE: keep until is not a dev-feature
    # raise HTTPNotFound(
    #     reason=f"Node '{path_params.project_id}/{path_params.node_id}' has no preview"
    # )
    #
    node_preview = _ProjectNodePreview(
        project_id=project.uuid,
        node_id=path_params.node_id,
        screenshots=await fake_screenshots_factory(request, path_params.node_id, node),
    )
    return envelope_json_response(node_preview)
