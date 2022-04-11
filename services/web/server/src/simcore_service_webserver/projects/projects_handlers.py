""" Handlers for on /projects colletions

Imports in standard methods (SEE projects_handlers_crud) and extends with
    - custom methods (https://google.aip.dev/121)
    - singleton resources (https://google.aip.dev/156)
    - ...
"""
import json
import logging

from aiohttp import web
from models_library.projects_state import ProjectState
from servicelib.aiohttp.web_exceptions_extension import HTTPLocked
from servicelib.json_serialization import json_dumps

from .._meta import api_version_prefix as VTAG
from ..director_v2_core import DirectorServiceError
from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import PROJECT_ID_KEY, managed_resource
from ..security_decorators import permission_required
from . import projects_api
from .projects_exceptions import ProjectNotFoundError
from .projects_handlers_crud import routes

log = logging.getLogger(__name__)

#
# Singleton per-user resources https://google.aip.dev/156
#


@routes.get(f"/{VTAG}/projects/active")
@login_required
@permission_required("project.read")
async def get_active_project(request: web.Request) -> web.Response:
    user_id: int = request[RQT_USERID_KEY]

    try:
        client_session_id = request.query["client_session_id"]

    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err
    try:
        project = None
        user_active_projects = []
        with managed_resource(user_id, client_session_id, request.app) as rt:
            # get user's projects
            user_active_projects = await rt.find(PROJECT_ID_KEY)
        if user_active_projects:

            project = await projects_api.get_project_for_user(
                request.app,
                project_uuid=user_active_projects[0],
                user_id=user_id,
                include_templates=True,
                include_state=True,
            )

        return web.json_response({"data": project}, dumps=json_dumps)

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason="Project not found") from exc


#
# Custom methods https://google.aip.dev/136
#


@routes.post(f"/{VTAG}/projects/{{project_uuid}}:open")
@login_required
@permission_required("project.open")
async def open_project(request: web.Request) -> web.Response:
    user_id: int = request[RQT_USERID_KEY]
    try:
        project_uuid = request.match_info["project_id"]
        client_session_id = await request.json()
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason="Invalid request body") from exc

    try:
        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=False,
            include_state=True,
        )

        if not await projects_api.try_open_project_for_user(
            user_id,
            project_uuid=project_uuid,
            client_session_id=client_session_id,
            app=request.app,
        ):
            raise HTTPLocked(reason="Project is locked, try later")

        # user id opened project uuid
        await projects_api.start_project_interactive_services(request, project, user_id)

        # notify users that project is now opened
        project = await projects_api.add_project_states_for_user(
            user_id=user_id,
            project=project,
            is_template=False,
            app=request.app,
        )

        await projects_api.notify_project_state_update(request.app, project)

        return web.json_response({"data": project}, dumps=json_dumps)

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc
    except DirectorServiceError as exc:
        # there was an issue while accessing the director-v2/director-v0
        # ensure the project is closed again
        await projects_api.try_close_project_for_user(
            user_id=user_id,
            project_uuid=project_uuid,
            client_session_id=client_session_id,
            app=request.app,
        )
        raise web.HTTPServiceUnavailable(
            reason="Unexpected error while starting services."
        ) from exc


@routes.post(f"/{VTAG}/projects/{{project_uuid}}:close")
@login_required
@permission_required("project.close")
async def close_project(request: web.Request) -> web.Response:
    user_id: int = request[RQT_USERID_KEY]
    try:
        project_uuid = request.match_info["project_id"]
        client_session_id = await request.json()

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
            include_templates=False,
            include_state=False,
        )
        await projects_api.try_close_project_for_user(
            user_id, project_uuid, client_session_id, request.app
        )
        raise web.HTTPNoContent(content_type="application/json")
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


@routes.get(f"/{VTAG}/projects/{{project_uuid}}/state")
@login_required
@permission_required("project.read")
async def state_project(request: web.Request) -> web.Response:
    from servicelib.aiohttp.rest_utils import extract_and_validate

    user_id: int = request[RQT_USERID_KEY]

    path, _, _ = await extract_and_validate(request)
    project_uuid = path["project_id"]

    # check that project exists and queries state
    validated_project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=project_uuid,
        user_id=user_id,
        include_templates=True,
        include_state=True,
    )
    project_state = ProjectState(**validated_project["state"])
    return web.json_response({"data": project_state.dict()}, dumps=json_dumps)
