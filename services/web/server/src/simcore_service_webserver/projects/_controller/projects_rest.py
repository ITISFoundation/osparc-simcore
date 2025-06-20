import logging

from aiohttp import web
from common_library.json_serialization import json_dumps
from models_library.api_schemas_webserver.projects import (
    EmptyModel,
    ProjectCopyOverride,
    ProjectCreateNew,
    ProjectGet,
    ProjectPatch,
)
from models_library.generics import Envelope
from models_library.projects_state import ProjectLocked
from models_library.rest_ordering import OrderBy
from models_library.utils.fastapi_encoders import jsonable_encoder
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
from servicelib.redis import get_project_locked_state

from ..._meta import API_VTAG as VTAG
from ...login.decorators import login_required
from ...redis import get_redis_lock_manager_client_sdk
from ...resource_manager.user_sessions import PROJECT_ID_KEY, managed_resource
from ...security import security_web
from ...security.decorators import permission_required
from ...users.api import get_user_fullname
from ...utils_aiohttp import envelope_json_response, get_api_base_url
from .. import _crud_api_create, _crud_api_read, _projects_service
from .._permalink_service import update_or_pop_permalink_in_project
from ..models import ProjectDict
from . import _rest_utils
from ._rest_exceptions import handle_plugin_requests_exceptions
from ._rest_schemas import (
    AuthenticatedRequestContext,
    ProjectPathParams,
)
from .projects_rest_schemas import (
    ProjectActiveQueryParams,
    ProjectCreateHeaders,
    ProjectCreateQueryParams,
    ProjectFilters,
    ProjectsListQueryParams,
    ProjectsSearchQueryParams,
)

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/projects", name="create_project")
@login_required
@permission_required("project.create")
@permission_required("services.pipeline.*")  # due to update_pipeline_db
@handle_plugin_requests_exceptions
async def create_project(request: web.Request):
    #
    # - Create https://google.aip.dev/133
    #
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    query_params: ProjectCreateQueryParams = parse_request_query_parameters_as(
        ProjectCreateQueryParams, request
    )
    header_params = parse_request_headers_as(ProjectCreateHeaders, request)
    if query_params.as_template:  # create template from
        await security_web.check_user_permission(request, "project.template.create")

    # NOTE: Having so many different types of bodys is an indication that
    # this entrypoint are in reality multiple entrypoints in one, namely
    # :create, :copy (w/ and w/o override)
    # NOTE: see clone_project
    predefined_project: ProjectDict | None

    if not request.can_read_body:
        # request w/o body
        predefined_project = None
    else:
        # request w/ body (I found cases in which body = {})
        project_create: ProjectCreateNew | ProjectCopyOverride | EmptyModel = (
            await parse_request_body_as(
                ProjectCreateNew | ProjectCopyOverride | EmptyModel,  # type: ignore[arg-type] # from pydantic v2 --> https://github.com/pydantic/pydantic/discussions/4950
                request,
            )
        )
        predefined_project = project_create.to_domain_model() or None

    return await start_long_running_task(
        request,
        _crud_api_create.create_project,  # type: ignore[arg-type] # @GitHK, @pcrespov this one I don't know how to fix
        fire_and_forget=True,
        task_context=jsonable_encoder(req_ctx),
        # arguments
        request=request,
        new_project_was_hidden_before_data_was_copied=query_params.hidden,
        from_study=query_params.from_study,
        as_template=query_params.as_template,
        copy_data=query_params.copy_data,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        product_api_base_url=get_api_base_url(request),
        simcore_user_agent=header_params.simcore_user_agent,
        predefined_project=predefined_project,
        parent_project_uuid=header_params.parent_project_uuid,
        parent_node_id=header_params.parent_node_id,
    )


@routes.get(f"/{VTAG}/projects", name="list_projects")
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def list_projects(request: web.Request):
    #
    # - List https://google.aip.dev/132
    #
    """

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of request parameters fail

    """
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    query_params: ProjectsListQueryParams = parse_request_query_parameters_as(
        ProjectsListQueryParams, request
    )

    if not query_params.filters:
        query_params.filters = ProjectFilters()

    assert query_params.filters  # nosec

    projects, total_number_of_projects = await _crud_api_read.list_projects(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        project_type=query_params.project_type,
        template_type=query_params.template_type,
        show_hidden=query_params.show_hidden,
        trashed=query_params.filters.trashed,
        folder_id=query_params.folder_id,
        workspace_id=query_params.workspace_id,
        search_by_multi_columns=query_params.search,
        search_by_project_name=query_params.filters.search_by_project_name,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
    )

    projects = await _rest_utils.aggregate_data_to_projects_from_request(
        request, projects
    )

    return _rest_utils.create_page_response(
        projects=projects,
        request_url=request.url,
        total=total_number_of_projects,
        limit=query_params.limit,
        offset=query_params.offset,
    )


@routes.get(f"/{VTAG}/projects:search", name="list_projects_full_search")
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def list_projects_full_search(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    query_params: ProjectsSearchQueryParams = parse_request_query_parameters_as(
        ProjectsSearchQueryParams, request
    )
    if not query_params.filters:
        query_params.filters = ProjectFilters()

    projects, total_number_of_projects = await _crud_api_read.list_projects_full_depth(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        trashed=query_params.filters.trashed,
        search_by_multi_columns=query_params.text,
        search_by_project_name=query_params.filters.search_by_project_name,
        offset=query_params.offset,
        limit=query_params.limit,
        order_by=OrderBy.model_construct(**query_params.order_by.model_dump()),
    )

    projects = await _rest_utils.aggregate_data_to_projects_from_request(
        request, projects
    )

    return _rest_utils.create_page_response(
        projects=projects,
        request_url=request.url,
        total=total_number_of_projects,
        limit=query_params.limit,
        offset=query_params.offset,
    )


@routes.get(f"/{VTAG}/projects/active", name="get_active_project")
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_active_project(request: web.Request) -> web.Response:
    #
    # - Get https://google.aip.dev/131
    # - Get active project: Singleton per-session resources https://google.aip.dev/156
    #
    """

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of request parameters fail
        web.HTTPNotFound: If active project is not found
    """
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    query_params: ProjectActiveQueryParams = parse_request_query_parameters_as(
        ProjectActiveQueryParams, request
    )

    user_active_projects = []
    with managed_resource(
        req_ctx.user_id, query_params.client_session_id, request.app
    ) as rt:
        # get user's projects
        user_active_projects = await rt.find(PROJECT_ID_KEY)

    data = None
    if user_active_projects:
        project = await _projects_service.get_project_for_user(
            request.app,
            project_uuid=user_active_projects[0],
            user_id=req_ctx.user_id,
            include_state=True,
            include_trashed_by_primary_gid=True,
        )

        # updates project's permalink field
        await update_or_pop_permalink_in_project(request, project)

        data = ProjectGet.from_domain_model(project).data(exclude_unset=True)

    return envelope_json_response(data)


@routes.get(f"/{VTAG}/projects/{{project_id}}", name="get_project")
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project(request: web.Request):
    """

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of request parameters fail
        web.HTTPNotFound: User has no access to at least one service in project
        web.HTTPForbidden: User has no access rights to get this project
        web.HTTPNotFound: This project was not found
    """

    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    project = await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=True,
        include_trashed_by_primary_gid=True,
    )

    # Adds permalink
    await update_or_pop_permalink_in_project(request, project)

    data = ProjectGet.from_domain_model(project).data(exclude_unset=True)
    return envelope_json_response(data)


@routes.get(
    f"/{VTAG}/projects/{{project_id}}/inactivity", name="get_project_inactivity"
)
@login_required
@permission_required("project.read")
@handle_plugin_requests_exceptions
async def get_project_inactivity(request: web.Request):
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    project_inactivity = await _projects_service.get_project_inactivity(
        app=request.app, project_id=path_params.project_id
    )
    return web.json_response(Envelope(data=project_inactivity), dumps=json_dumps)


@routes.patch(f"/{VTAG}/projects/{{project_id}}", name="patch_project")
@login_required
@permission_required("project.update")
@permission_required("services.pipeline.*")
@handle_plugin_requests_exceptions
async def patch_project(request: web.Request):
    #
    # Update https://google.aip.dev/134
    #
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    project_patch = await parse_request_body_as(ProjectPatch, request)

    await _projects_service.patch_project(
        request.app,
        user_id=req_ctx.user_id,
        project_uuid=path_params.project_id,
        project_patch=project_patch,
        product_name=req_ctx.product_name,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.delete(f"/{VTAG}/projects/{{project_id}}", name="delete_project")
@login_required
@permission_required("project.delete")
@handle_plugin_requests_exceptions
async def delete_project(request: web.Request):
    # Delete https://google.aip.dev/135
    """

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of request parameters fail
        web.HTTPForbidden: Still open in a different tab
        web.HTTPForbidden: Still open by another user
        web.HTTPConflict: Project is locked
        web.HTTPForbidden: Not enough access rights to delete this project
        web.HTTPNotFound: This project was not found
        web.HTTPConflict: Somethine went wrong while deleting
        web.HTTPNoContent: Sucess
    """
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    await _projects_service.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
    )
    project_users: set[int] = set()
    with managed_resource(req_ctx.user_id, None, request.app) as user_session:
        project_users = {
            s.user_id
            for s in await user_session.find_users_of_resource(
                request.app, PROJECT_ID_KEY, f"{path_params.project_id}"
            )
        }
    # that project is still in use
    if req_ctx.user_id in project_users:
        raise web.HTTPForbidden(
            text="Project is still open in another tab/browser."
            "It cannot be deleted until it is closed."
        )
    if project_users:
        other_user_names = {
            f"{await get_user_fullname(request.app, user_id=uid)}"
            for uid in project_users
        }
        raise web.HTTPForbidden(
            text=f"Project is open by {other_user_names}. "
            "It cannot be deleted until the project is closed."
        )

    project_locked_state: ProjectLocked | None
    if project_locked_state := await get_project_locked_state(
        get_redis_lock_manager_client_sdk(request.app),
        project_uuid=path_params.project_id,
    ):
        raise web.HTTPConflict(
            text=f"Project {path_params.project_id} is locked: {project_locked_state=}"
        )

    await _projects_service.submit_delete_project_task(
        request.app,
        project_uuid=path_params.project_id,
        user_id=req_ctx.user_id,
        simcore_user_agent=request.headers.get(
            X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
        ),
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# - Clone (as custom method)
#   - https://google.aip.dev/136
#   - https://cloud.google.com/apis/design/custom_methods#http_mapping
#


@routes.post(f"/{VTAG}/projects/{{project_id}}:clone", name="clone_project")
@login_required
@permission_required("project.create")
@permission_required("services.pipeline.*")  # due to update_pipeline_db
@handle_plugin_requests_exceptions
async def clone_project(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    return await start_long_running_task(
        request,
        _crud_api_create.create_project,  # type: ignore[arg-type] # @GitHK, @pcrespov this one I don't know how to fix
        fire_and_forget=True,
        task_context=jsonable_encoder(req_ctx),
        # arguments
        request=request,
        new_project_was_hidden_before_data_was_copied=False,
        from_study=path_params.project_id,
        as_template=False,
        copy_data=True,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        product_api_base_url=get_api_base_url(request),
        simcore_user_agent=request.headers.get(
            X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
        ),
        predefined_project=None,
        parent_project_uuid=None,
        parent_node_id=None,
    )
