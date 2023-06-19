""" Handlers for CRUD operations on /projects/{*}/nodes/{*}

"""

import asyncio
import functools
import json
import logging
from typing import Any

from aiohttp import web
from aiohttp.web_exceptions import HTTPNotFound
from models_library.api_schemas_catalog import ServiceAccessRightsGet
from models_library.groups import EVERYONE_GROUP_ID
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import NodeIDStr
from models_library.services import ServiceKey, ServiceKeyVersion, ServiceVersion
from models_library.users import GroupID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, Field, HttpUrl, parse_obj_as
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

from .._constants import APP_SETTINGS_KEY
from .._meta import api_version_prefix as VTAG
from ..catalog import client as catalog_client
from ..director_v2 import api
from ..director_v2.exceptions import DirectorServiceError
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..users.api import get_user_role
from ..utils_aiohttp import envelope_json_response
from . import projects_api
from ._handlers_crud import ProjectPathParams, RequestContext
from .db import ProjectDBAPI
from .exceptions import (
    NodeNotFoundError,
    ProjectNotFoundError,
    ProjectStartsTooManyDynamicNodes,
)

log = logging.getLogger(__name__)


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


class _CreateNodeBody(BaseModel):
    service_key: ServiceKey
    service_version: ServiceVersion
    service_id: str | None = None


@routes.post(f"/{VTAG}/projects/{{project_id}}/nodes")
@login_required
@permission_required("project.node.create")
@_handle_project_nodes_exceptions
async def create_node(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    body = await parse_request_body_as(_CreateNodeBody, request)

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
    return envelope_json_response(data, status_cls=web.HTTPCreated)


class _NodePathParams(ProjectPathParams):
    node_id: NodeID


@routes.get(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}")
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
            return envelope_json_response(service_data)

        # LEGACY-service NODE STATE
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


@routes.post(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:retrieve")
@login_required
@permission_required("project.node.read")
@_handle_project_nodes_exceptions
async def retrieve_node(request: web.Request) -> web.Response:
    """Has only effect on nodes associated to dynamic services"""
    path_params = parse_request_path_parameters_as(_NodePathParams, request)

    try:
        data = await request.json()
        port_keys = data.get("port_keys", [])
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason=f"Invalid request body: {exc}") from exc

    return web.json_response(
        await api.retrieve(request.app, f"{path_params.node_id}", port_keys),
        dumps=json_dumps,
    )


@routes.post(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:start")
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

    except ProjectStartsTooManyDynamicNodes as exc:
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


@routes.post(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:stop")
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


@routes.post(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}:restart")
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


@routes.get(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/resources")
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

    resources = await projects_api.get_project_node_resources(
        request.app,
        user_id=req_ctx.user_id,
        project=project,
        node_id=path_params.node_id,
    )
    return envelope_json_response(resources)


@routes.put(f"/{VTAG}/projects/{{project_id}}/nodes/{{node_id}}/resources")
@login_required
@permission_required("project.node.update")
@_handle_project_nodes_exceptions
async def replace_node_resources(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_NodePathParams, request)

    try:
        _body = await request.json()
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason=f"Invalid request body: {exc}") from exc

    # ensure the project exists
    _project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    raise web.HTTPNotImplemented(reason="Not yet implemented!")
    # NOTE: SAN? This your code?
    #
    # new_node_resources = await projects_api.set_project_node_resources(
    #     request.app, project=project, node_id=node_id
    # )

    # return envelope_json_response(new_node_resources)


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


class _NodeScreenshot(BaseModel):
    thumbnail_url: HttpUrl
    file_url: HttpUrl


def _fake_screenshots_factory(
    request: web.Request, node_id: NodeID
) -> list[_NodeScreenshot]:
    assert request.app[APP_SETTINGS_KEY].WEBSERVER_DEV_FEATURES_ENABLED  # nosec
    # https://placehold.co/
    # https://picsum.photos/
    short_nodeid = str(node_id)[4:]
    count = int(str(node_id.int)[-1])
    seed = short_nodeid
    return [
        _NodeScreenshot(
            thumbnail_url=f"https://placehold.co/170x120?text={short_nodeid}",
            file_url=f"https://picsum.photos/seed/{seed}/500",
        )
        for _ in range(count)
    ]


class _ProjectNodePreview(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    screenshots: list[_NodeScreenshot] = Field(default_factory=list)


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

    nodes_previews = []

    if request.app[APP_SETTINGS_KEY].WEBSERVER_DEV_FEATURES_ENABLED:
        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
        )

        node_ids = parse_obj_as(list[NodeID], list(project.get("workbench", {}).keys()))
        nodes_previews = [
            _ProjectNodePreview(
                project_id=path_params.project_id,
                node_id=node_id,
                screenshots=_fake_screenshots_factory(request, node_id),
            )
            for node_id in node_ids
        ]

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

    if request.app[APP_SETTINGS_KEY].WEBSERVER_DEV_FEATURES_ENABLED:

        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
        )

        if path_params.node_id not in parse_obj_as(
            list[NodeID], list(project.get("workbench", {}).keys())
        ):
            raise NodeNotFoundError(
                project_uuid=f"{path_params.project_id}",
                node_uuid=f"{path_params.node_id}",
            )

        node_home_page = _ProjectNodePreview(
            project_id=project["uuid"],
            node_id=path_params.node_id,
            screenshots=_fake_screenshots_factory(request, path_params.node_id),
        )
        return envelope_json_response(node_home_page)

    raise HTTPNotFound(
        reason=f"node {path_params.project_id}/{path_params.node_id} has no homepage"
    )
