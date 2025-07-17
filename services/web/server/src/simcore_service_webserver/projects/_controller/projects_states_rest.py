import contextlib
import json
import logging

from aiohttp import web
from models_library.api_schemas_webserver.projects import ProjectGet
from pydantic import BaseModel
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.web_exceptions_extension import HTTPLockedError
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.webserver_models import ProjectType

from ..._meta import API_VTAG as VTAG
from ...application_settings import get_application_settings
from ...director_v2.exceptions import DirectorV2ServiceError
from ...login.decorators import login_required
from ...notifications import project_logs
from ...products import products_web
from ...products.models import Product
from ...security.decorators import permission_required
from ...users import users_service
from ...utils_aiohttp import envelope_json_response, get_api_base_url
from .. import _projects_service, projects_wallets_service
from ..exceptions import ProjectStartsTooManyDynamicNodesError
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import AuthenticatedRequestContext, ProjectPathParams

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


#
# open project: custom methods https://google.aip.dev/136
#


class _OpenProjectQuery(BaseModel):
    disable_service_auto_start: bool = False


@routes.post(f"/{VTAG}/projects/{{project_id}}:open", name="open_project")
@login_required
@permission_required("project.open")
@handle_plugin_requests_exceptions
async def open_project(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    query_params: _OpenProjectQuery = parse_request_query_parameters_as(
        _OpenProjectQuery, request
    )

    try:
        client_session_id = await request.json()

    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(text="Invalid request body") from exc

    try:
        project_type: ProjectType = await _projects_service.get_project_type(
            request.app, path_params.project_id
        )
        user_role: UserRole = await users_service.get_user_role(
            request.app, user_id=req_ctx.user_id
        )
        if project_type is ProjectType.TEMPLATE and user_role < UserRole.USER:
            # only USERS/TESTERS can do that
            raise web.HTTPForbidden(text="Wrong user role to open/edit a template")

        project = await _projects_service.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
            include_state=True,
            check_permissions=(
                "write" if project_type is ProjectType.TEMPLATE else "read"
            ),
        )

        await projects_wallets_service.check_project_financial_status(
            request.app,
            project_id=path_params.project_id,
            product_name=req_ctx.product_name,
        )

        product: Product = products_web.get_current_product(request)
        app_settings = get_application_settings(request.app)

        if not await _projects_service.try_open_project_for_user(
            req_ctx.user_id,
            project_uuid=path_params.project_id,
            client_session_id=client_session_id,
            app=request.app,
            max_number_of_opened_projects_per_user=product.max_open_studies_per_user,
            max_number_of_user_sessions_per_project=(
                1
                if not app_settings.WEBSERVER_REALTIME_COLLABORATION
                else app_settings.WEBSERVER_REALTIME_COLLABORATION.RTC_MAX_NUMBER_OF_USERS
            ),
        ):
            raise HTTPLockedError(text="Project is locked, try later")

        # the project can be opened, let's update its product links
        await _projects_service.update_project_linked_product(
            request.app, path_params.project_id, req_ctx.product_name
        )

        # we now need to receive logs for that project
        await project_logs.subscribe(request.app, path_params.project_id)

        # user id opened project uuid
        if not query_params.disable_service_auto_start:
            with contextlib.suppress(ProjectStartsTooManyDynamicNodesError):
                # NOTE: this method raises that exception when the number of dynamic
                # services in the project is highter than the maximum allowed per project
                # the project shall still open though.
                await _projects_service.run_project_dynamic_services(
                    request,
                    project,
                    req_ctx.user_id,
                    req_ctx.product_name,
                    get_api_base_url(request),
                )

        # and let's update the project last change timestamp
        await _projects_service.update_project_last_change_timestamp(
            request.app, path_params.project_id
        )

        # notify users that project is now opened
        project = await _projects_service.add_project_states_for_user(
            user_id=req_ctx.user_id,
            project=project,
            is_template=False,
            app=request.app,
        )
        await _projects_service.notify_project_state_update(request.app, project)

        return envelope_json_response(ProjectGet.from_domain_model(project))

    except DirectorV2ServiceError as exc:
        # there was an issue while accessing the director-v2/director-v0
        # ensure the project is closed again
        await _projects_service.try_close_project_for_user(
            user_id=req_ctx.user_id,
            project_uuid=f"{path_params.project_id}",
            client_session_id=client_session_id,
            app=request.app,
            simcore_user_agent=request.headers.get(
                X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
            ),
        )
        raise web.HTTPServiceUnavailable(
            text="Unexpected error while starting services."
        ) from exc


#
# close project: custom methods https://google.aip.dev/136
#


@routes.post(f"/{VTAG}/projects/{{project_id}}:close", name="close_project")
@login_required
@permission_required("project.close")
@handle_plugin_requests_exceptions
async def close_project(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    try:
        client_session_id = await request.json()

    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(text="Invalid request body") from exc

    # ensure the project exists
    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )
    await _projects_service.try_close_project_for_user(
        req_ctx.user_id,
        f"{path_params.project_id}",
        client_session_id,
        request.app,
        simcore_user_agent=request.headers.get(
            X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
        ),
    )
    await project_logs.unsubscribe(request.app, path_params.project_id)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# project's state sub-resource
#


@routes.get(f"/{VTAG}/projects/{{project_id}}/state", name="get_project_state")
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_state(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    # check that project exists and queries state
    project = await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=True,
    )
    project_state = ProjectGet.from_domain_model(project).state
    assert project_state  # nosec
    return envelope_json_response(
        project_state.model_dump(
            **RESPONSE_MODEL_POLICY,
        )
    )
