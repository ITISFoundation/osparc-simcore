""" Handlers for CRUD operations on /projects/{*}/nodes/{*}

"""

import json
import logging
from typing import Dict, List, Union

from aiohttp import web

from .. import director_v2
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_decorators import permission_required
from . import projects_api
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import ProjectNotFoundError

log = logging.getLogger(__name__)


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
        return web.json_response({"data": data}, status=web.HTTPCreated.status_code)
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


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
        reply: Union[Dict, List] = await director_v2.get_service_state(
            app=request.app, node_uuid=node_uuid
        )

        if "data" not in reply:
            # dynamic-service NODE STATE
            return web.json_response({"data": reply})

        # LEGACY-service NODE STATE
        return web.json_response({"data": reply["data"]})
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


@login_required
@permission_required("project.node.read")
async def get_retrieve(request: web.Request) -> web.Response:
    try:
        node_uuid = request.match_info["node_id"]
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    return web.json_response(director_v2.retrieve(request.app, node_uuid))


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


@login_required
@permission_required("project.tag.*")
async def add_tag(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    try:
        tag_id, study_uuid = (
            request.match_info["tag_id"],
            request.match_info["study_uuid"],
        )
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    return await db.add_tag(
        project_uuid=study_uuid, user_id=user_id, tag_id=int(tag_id)
    )


@login_required
@permission_required("project.tag.*")
async def remove_tag(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    tag_id, study_uuid = (
        request.match_info["tag_id"],
        request.match_info["study_uuid"],
    )
    return await db.remove_tag(
        project_uuid=study_uuid, user_id=user_id, tag_id=int(tag_id)
    )
