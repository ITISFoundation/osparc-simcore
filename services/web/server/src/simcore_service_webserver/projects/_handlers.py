""" Handlers for on /projects colletions

Imports in standard methods (SEE _handlers_crud) and extends with
    - custom methods (https://google.aip.dev/121)

"""
import contextlib
import json
import logging

from aiohttp import web
from models_library.projects_state import ProjectState
from pydantic import BaseModel
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.web_exceptions_extension import HTTPLocked
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.webserver_models import ProjectType

from .._meta import api_version_prefix as VTAG
from ..director_v2.exceptions import DirectorServiceError
from ..login.decorators import login_required
from ..notifications import project_logs
from ..products.plugin import Product, get_current_product
from ..security.decorators import permission_required
from ..users import api
from . import projects_api
from ._handlers_crud import ProjectPathParams, RequestContext
from .exceptions import (
    ProjectInvalidRightsError,
    ProjectNotFoundError,
    ProjectStartsTooManyDynamicNodes,
    ProjectTooManyProjectOpened,
)

log = logging.getLogger(__name__)


routes = web.RouteTableDef()


class _OpenProjectQuery(BaseModel):
    disable_service_auto_start: bool = False


@routes.post(f"/{VTAG}/projects/{{project_id}}:open", name="open_project")
@login_required
@permission_required("project.open")
async def open_project(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    query_params = parse_request_query_parameters_as(_OpenProjectQuery, request)

    try:
        client_session_id = await request.json()

    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason="Invalid request body") from exc

    try:
        project_type: ProjectType = await projects_api.get_project_type(
            request.app, path_params.project_id
        )
        user_role: UserRole = await api.get_user_role(request.app, req_ctx.user_id)
        if project_type is ProjectType.TEMPLATE and user_role < UserRole.USER:
            # only USERS/TESTERS can do that
            raise web.HTTPForbidden(reason="Wrong user role to open/edit a template")

        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
            include_state=True,
            check_permissions="read|write"
            if project_type is ProjectType.TEMPLATE
            else "read",
        )

        product: Product = get_current_product(request)

        if not await projects_api.try_open_project_for_user(
            req_ctx.user_id,
            project_uuid=f"{path_params.project_id}",
            client_session_id=client_session_id,
            app=request.app,
            max_number_of_studies_per_user=product.max_open_studies_per_user,
        ):
            raise HTTPLocked(reason="Project is locked, try later")

        # the project can be opened, let's update its product links
        await projects_api.update_project_linked_product(
            request.app, path_params.project_id, req_ctx.product_name
        )

        # we now need to receive logs for that project
        await project_logs.subscribe(request.app, path_params.project_id)

        # user id opened project uuid
        if not query_params.disable_service_auto_start:
            with contextlib.suppress(ProjectStartsTooManyDynamicNodes):
                # NOTE: this method raises that exception when the number of dynamic
                # services in the project is highter than the maximum allowed per project
                # the project shall still open though.
                await projects_api.run_project_dynamic_services(
                    request, project, req_ctx.user_id, req_ctx.product_name
                )

        # and let's update the project last change timestamp
        await projects_api.update_project_last_change_timestamp(
            request.app, path_params.project_id
        )

        # notify users that project is now opened
        project = await projects_api.add_project_states_for_user(
            user_id=req_ctx.user_id,
            project=project,
            is_template=False,
            app=request.app,
        )
        await projects_api.notify_project_state_update(request.app, project)

        return web.json_response({"data": project}, dumps=json_dumps)

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(
            reason=f"Project {path_params.project_id} not found"
        ) from exc
    except DirectorServiceError as exc:
        # there was an issue while accessing the director-v2/director-v0
        # ensure the project is closed again
        await projects_api.try_close_project_for_user(
            user_id=req_ctx.user_id,
            project_uuid=f"{path_params.project_id}",
            client_session_id=client_session_id,
            app=request.app,
            simcore_user_agent=request.headers.get(
                X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
            ),
        )
        raise web.HTTPServiceUnavailable(
            reason="Unexpected error while starting services."
        ) from exc
    except ProjectTooManyProjectOpened as exc:
        raise web.HTTPConflict(reason=f"{exc}") from exc
    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason=f"You do not have sufficient rights to access project {path_params.project_id}"
        ) from exc


#
# close project: custom methods https://google.aip.dev/136
#


@routes.post(f"/{VTAG}/projects/{{project_id}}:close", name="close_project")
@login_required
@permission_required("project.close")
async def close_project(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    try:
        client_session_id = await request.json()

    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason="Invalid request body") from exc

    try:
        # ensure the project exists
        await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
            include_state=False,
        )
        await projects_api.try_close_project_for_user(
            req_ctx.user_id,
            f"{path_params.project_id}",
            client_session_id,
            request.app,
            simcore_user_agent=request.headers.get(
                X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
            ),
        )
        await project_logs.unsubscribe(request.app, path_params.project_id)
        raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(
            reason=f"Project {path_params.project_id} not found"
        ) from exc


#
# project's state sub-resource
#


@routes.get(f"/{VTAG}/projects/{{project_id}}/state", name="get_project_state")
@login_required
@permission_required("project.read")
async def get_project_state(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    # check that project exists and queries state
    validated_project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=True,
    )
    project_state = ProjectState(**validated_project["state"])
    return web.json_response({"data": project_state.dict()}, dumps=json_dumps)
