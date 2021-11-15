""" Handlers for CRUD operations on /projects/{*}/nodes/{*}

"""

import json
import logging
from typing import Dict, List, Union

from aiohttp import web
from servicelib.json_serialization import json_dumps

from .. import director_v2_api
from .._meta import api_version_prefix as VTAG
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_decorators import permission_required
from . import projects_api
from .projects_exceptions import ProjectNotFoundError

log = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/projects/{{project_uuid}}/nodes")
@login_required
@permission_required("project.node.create")
async def create_node(request: web.Request) -> web.Response:
    user_id: int = request[RQT_USERID_KEY]

    try:
        project_uuid = request.match_info["project_id"]
        body = await request.json()
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason="Invalid request body") from exc
    try:
        # ensure the project exists

        await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )
        data = {
            "node_id": await projects_api.add_project_node(
                request,
                project_uuid,
                user_id,
                body["service_key"],
                body["service_version"],
                body["service_id"] if "service_id" in body else None,
            )
        }
        return web.json_response(
            {"data": data}, status=web.HTTPCreated.status_code, dumps=json_dumps
        )
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


@routes.get(f"/{VTAG}/projects/{{project_uuid}}/nodes/{{node_uuid}}")
@login_required
@permission_required("project.node.read")
async def get_node(request: web.Request) -> web.Response:
    user_id: int = request[RQT_USERID_KEY]

    try:
        project_uuid = request.match_info["project_id"]
        node_uuid = request.match_info["node_id"]

    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    try:
        # ensure the project exists

        await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )

        # NOTE: for legacy services a redirect to director-v0 is made
        reply: Union[Dict, List] = await director_v2_api.get_service_state(
            app=request.app, node_uuid=node_uuid
        )

        if "data" not in reply:
            # dynamic-service NODE STATE
            return web.json_response({"data": reply}, dumps=json_dumps)

        # LEGACY-service NODE STATE
        return web.json_response({"data": reply["data"]}, dumps=json_dumps)
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


@routes.delete(f"/{VTAG}/projects/{{project_uuid}}/nodes/{{node_uuid}}")
@login_required
@permission_required("project.node.read")
async def post_retrieve(request: web.Request) -> web.Response:
    try:
        node_uuid = request.match_info["node_id"]
        data = await request.json()
        port_keys = data.get("port_keys", [])
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    return web.json_response(
        await director_v2_api.retrieve(request.app, node_uuid, port_keys),
        dumps=json_dumps,
    )


@login_required
@permission_required("project.node.delete")
async def delete_node(request: web.Request) -> web.Response:
    user_id: int = request[RQT_USERID_KEY]

    try:
        project_uuid = request.match_info["project_id"]
        node_uuid = request.match_info["node_id"]

    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    try:
        # ensure the project exists

        await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )

        await projects_api.delete_project_node(
            request, project_uuid, user_id, node_uuid
        )

        raise web.HTTPNoContent(content_type="application/json")
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc
