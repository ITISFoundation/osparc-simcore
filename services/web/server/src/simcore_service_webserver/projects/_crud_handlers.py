""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""
import json
import logging

from aiohttp import web
from jsonschema import ValidationError as JsonSchemaValidationError
from models_library.api_schemas_webserver.projects import (
    EmptyModel,
    ProjectCopyOverride,
    ProjectCreateNew,
    ProjectGet,
    ProjectUpdate,
)
from models_library.projects import Project, ProjectID
from models_library.projects_state import ProjectLocked
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
)
from models_library.rest_pagination_utils import paginate_data
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, Extra, Field, NonNegativeInt, validator
from servicelib.aiohttp.long_running_tasks.server import start_long_running_task
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import api_version_prefix as VTAG
from ..catalog.client import get_services_for_user_in_product
from ..director_v2 import api
from ..login.decorators import login_required
from ..resource_manager.user_sessions import PROJECT_ID_KEY, managed_resource
from ..security.api import check_permission
from ..security.decorators import permission_required
from ..users.api import get_user_name
from . import _crud_api_create, _crud_api_read, projects_api
from ._common_models import ProjectPathParams, RequestContext
from ._crud_api_read import OrderDirection, ProjectListFilters, ProjectOrderBy
from ._permalink_api import update_or_pop_permalink_in_project
from .db import ProjectDBAPI
from .exceptions import (
    ProjectDeleteError,
    ProjectInvalidRightsError,
    ProjectNotFoundError,
)
from .lock import get_project_locked_state
from .models import ProjectDict, ProjectTypeAPI
from .nodes_utils import update_frontend_outputs
from .utils import (
    any_node_inputs_changed,
    get_project_unavailable_services,
    project_uses_available_services,
    replace_multiple_spaces,
)

# When the user requests a project with a repo, the working copy might differ from
# the repo project. A middleware in the meta module (if active) will resolve
# the working copy and redirect to the appropriate project entrypoint. Nonetheless, the
# response needs to refer to the uuid of the request and this is passed through this request key
RQ_REQUESTED_REPO_PROJECT_UUID_KEY = f"{__name__}.RQT_REQUESTED_REPO_PROJECT_UUID_KEY"


_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


#
# - Create https://google.aip.dev/133
#


class _ProjectCreateParams(BaseModel):
    from_study: ProjectID | None = Field(
        None,
        description="Option to create a project from existing template or study: from_study={study_uuid}",
    )
    as_template: bool = Field(
        default=False,
        description="Option to create a template from existing project: as_template=true",
    )
    copy_data: bool = Field(
        default=True,
        description="Option to copy data when creating from an existing template or as a template, defaults to True",
    )
    hidden: bool = Field(
        default=False,
        description="Enables/disables hidden flag. Hidden projects are by default unlisted",
    )

    class Config:
        extra = Extra.forbid


@routes.post(f"/{VTAG}/projects", name="create_project")
@login_required
@permission_required("project.create")
@permission_required("services.pipeline.*")  # due to update_pipeline_db
async def create_project(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ProjectCreateParams, request)
    if query_params.as_template:  # create template from
        await check_permission(request, "project.template.create")

    # NOTE: Having so many different types of bodys is an indication that
    # this entrypoint are in reality multiple entrypoints in one, namely
    # :create, :copy (w/ and w/o override)
    #
    if not request.can_read_body:
        # request w/o body
        assert query_params.from_study  # nosec
        predefined_project = None
    else:
        # request w/ body (I found cases in which body = {})
        project_create = await parse_request_body_as(
            ProjectCreateNew | ProjectCopyOverride | EmptyModel, request
        )
        predefined_project = (
            project_create.dict(
                exclude_unset=True,
                by_alias=True,
                exclude_none=True,
            )
            or None
        )

    return await start_long_running_task(
        request,
        _crud_api_create.create_project,
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
        simcore_user_agent=request.headers.get(
            X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
        ),
        predefined_project=predefined_project,
    )


#
# - List https://google.aip.dev/132
#


class _ProjectListParams(BaseModel):
    limit: int = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
        ge=1,
        lt=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    )
    offset: NonNegativeInt = Field(
        default=0, description="index to the first item to return (pagination)"
    )
    project_type: ProjectTypeAPI = Field(default=ProjectTypeAPI.all, alias="type")
    show_hidden: bool = Field(
        default=False, description="includes projects marked as hidden in the listing"
    )

    order_by: list[ProjectOrderBy] | None = Field(
        default=None,
        description="Comma separated list of fields for ordering. The default sorting order is ascending. To specify descending order for a field, users append a 'desc' suffix",
        example="foo desc, bar",
    )
    filters: ProjectListFilters | None = Field(
        default=None,
        description="Filters to process on the projects list, encoded as JSON",
        example='{"tags": [1, 5], "classifiers": ["foo", "bar"]}',
    )
    search: str | None = Field(
        default=None,
        description="Multi column full text search",
        max_length=100,
        example="My Project",
    )

    @validator("order_by", pre=True)
    @classmethod
    def sort_by_should_have_special_format(cls, v):
        if not v:
            return v

        parse_fields_with_direction = []
        fields = v.split(",")
        for field in fields:
            field_info = replace_multiple_spaces(field.strip()).split(" ")
            field_name = field_info[0]
            direction = OrderDirection.ASC

            if len(field_info) == 2:
                if field_info[1] == OrderDirection.DESC.value:
                    direction = OrderDirection.DESC
                else:
                    msg = "Field direction in the order_by parameter must contain either 'desc' direction or empty value for 'asc' direction."
                    raise ValueError(msg)

            parse_fields_with_direction.append(
                ProjectOrderBy(field=field_name, direction=direction)
            )

        return parse_fields_with_direction

    @validator("filters", pre=True)
    @classmethod
    def filters_parse_to_object(cls, v):
        if v:
            v = json.loads(v)
        return v

    @validator("search", pre=True)
    @classmethod
    def search_check_empty_string(cls, v):
        if not v:
            return None
        return v

    class Config:
        extra = Extra.forbid


@routes.get(f"/{VTAG}/projects", name="list_projects")
@login_required
@permission_required("project.read")
async def list_projects(request: web.Request):
    """

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of request parameters fail

    """
    req_ctx = RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ProjectListParams, request)

    projects, total_number_of_projects = await _crud_api_read.list_projects(
        request,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        project_type=query_params.project_type,
        show_hidden=query_params.show_hidden,
        limit=query_params.limit,
        offset=query_params.offset,
        search=query_params.search,
    )

    page = Page[ProjectDict].parse_obj(
        paginate_data(
            chunk=projects,
            request_url=request.url,
            total=total_number_of_projects,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


#
# - Get https://google.aip.dev/131
# - Get active project: Singleton per-session resources https://google.aip.dev/156
#


class _ProjectActiveParams(BaseModel):
    client_session_id: str


@routes.get(f"/{VTAG}/projects/active", name="get_active_project")
@login_required
@permission_required("project.read")
async def get_active_project(request: web.Request) -> web.Response:
    """

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of request parameters fail
        web.HTTPNotFound: If active project is not found
    """
    req_ctx = RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ProjectActiveParams, request)

    try:
        user_active_projects = []
        with managed_resource(
            req_ctx.user_id, query_params.client_session_id, request.app
        ) as rt:
            # get user's projects
            user_active_projects = await rt.find(PROJECT_ID_KEY)

        data = None
        if user_active_projects:
            project = await projects_api.get_project_for_user(
                request.app,
                project_uuid=user_active_projects[0],
                user_id=req_ctx.user_id,
                include_state=True,
            )

            # updates project's permalink field
            await update_or_pop_permalink_in_project(request, project)

            data = ProjectGet.parse_obj(project).data(exclude_unset=True)

        return web.json_response({"data": data}, dumps=json_dumps)

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason="Project not found") from exc


@routes.get(f"/{VTAG}/projects/{{project_id}}", name="get_project")
@login_required
@permission_required("project.read")
async def get_project(request: web.Request):
    """

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of request parameters fail
        web.HTTPNotFound: User has no access to at least one service in project
        web.HTTPForbidden: User has no access rights to get this project
        web.HTTPNotFound: This project was not found
    """

    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    user_available_services: list[dict] = await get_services_for_user_in_product(
        request.app, req_ctx.user_id, req_ctx.product_name, only_key_versions=True
    )

    try:
        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
            include_state=True,
        )
        if not await project_uses_available_services(project, user_available_services):
            unavilable_services = get_project_unavailable_services(
                project, user_available_services
            )
            formatted_services = ", ".join(
                f"{service}:{version}" for service, version in unavilable_services
            )
            # TODO: lack of permissions should be notified with https://httpstatuses.com/403 web.HTTPForbidden
            raise web.HTTPNotFound(
                reason=(
                    f"Project '{path_params.project_id}' uses unavailable services. Please ask "
                    f"for permission for the following services {formatted_services}"
                )
            )

        if new_uuid := request.get(RQ_REQUESTED_REPO_PROJECT_UUID_KEY):
            project["uuid"] = new_uuid

        # Adds permalink
        await update_or_pop_permalink_in_project(request, project)

        data = ProjectGet.parse_obj(project).data(exclude_unset=True)
        return web.json_response({"data": data}, dumps=json_dumps)

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason=f"You do not have sufficient rights to read project {path_params.project_id}"
        ) from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(
            reason=f"Project {path_params.project_id} not found"
        ) from exc


#
# - Update https://google.aip.dev/134
#


@routes.put(f"/{VTAG}/projects/{{project_id}}", name="replace_project")
@login_required
@permission_required("project.update")
@permission_required("services.pipeline.*")  # due to update_pipeline_db
async def replace_project(request: web.Request):
    """
    In a PUT request, the enclosed entity is considered to be a modified version of
    the resource stored on the origin server, and the client is requesting that the
    stored version be replaced.

    With PATCH, however, the enclosed entity contains a set of instructions describing how a
    resource currently residing on the origin server should be modified to produce a new version.

    Also, another difference is that when you want to update a resource with PUT request, you have to send
    the full payload as the request whereas with PATCH, you only send the parameters which you want to update.

    Raises:
       web.HTTPUnprocessableEntity: (422) if validation of request parameters fail
       web.HTTPBadRequest: invalid body encoding
       web.HTTPConflict: Cannot replace while pipeline is running
       web.HTTPBadRequest: jsonschema validatio error
       web.HTTPForbidden: Not enough access rights to replace this project
       web.HTTPNotFound: This project was not found
    """

    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    try:
        new_project = await request.json()
        # NOTE: this is a temporary fix until proper Model is introduced in ProjectReplace
        # Prune state field (just in case)
        new_project.pop("state", None)
        new_project.pop("permalink", None)

    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason="Invalid request body") from exc

    await check_permission(
        request,
        "project.update | project.workbench.node.inputs.update",
        context={
            "dbapi": db,
            "project_id": f"{path_params.project_id}",
            "user_id": req_ctx.user_id,
            "new_data": new_project,
        },
    )

    try:
        Project.parse_obj(new_project)  # validate

        current_project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
            include_state=True,
        )

        if current_project["accessRights"] != new_project["accessRights"]:
            await check_permission(request, "project.access_rights.update")

        if await api.is_pipeline_running(
            request.app, req_ctx.user_id, path_params.project_id
        ):
            if any_node_inputs_changed(new_project, current_project):
                # NOTE:  This is a conservative measure that we take
                #  until nodeports logic is re-designed to tackle with this
                #  particular state.
                #
                # This measure avoid having a state with different node *links* in the
                # comp-tasks table and the project's workbench column.
                # The limitation is that nodeports only "sees" those in the comptask
                # and this table does not add the new ones since it remains "blocked"
                # for modification from that project while the pipeline runs. Therefore
                # any extra link created while the pipeline is running can not
                # be managed by nodeports because it basically "cannot see it"
                #
                # Responds https://httpstatuses.com/409:
                #  The request could not be completed due to a conflict with the current
                #  state of the target resource (i.e. pipeline is running). This code is used in
                #  situations where the user might be able to resolve the conflict
                #  and resubmit the request  (front-end will show a pop-up with message below)
                #
                raise web.HTTPConflict(
                    reason=f"Project {path_params.project_id} cannot be modified while pipeline is still running."
                )

        new_project = await db.replace_project(
            new_project,
            req_ctx.user_id,
            project_uuid=f"{path_params.project_id}",
            product_name=req_ctx.product_name,
        )

        await update_frontend_outputs(
            app=request.app,
            user_id=req_ctx.user_id,
            project_uuid=path_params.project_id,
            old_project=current_project,
            new_project=new_project,
        )

        await api.update_dynamic_service_networks_in_project(
            request.app, path_params.project_id
        )
        await api.create_or_update_pipeline(
            request.app,
            req_ctx.user_id,
            path_params.project_id,
            product_name=req_ctx.product_name,
        )
        # Appends state
        data = await projects_api.add_project_states_for_user(
            user_id=req_ctx.user_id,
            project=new_project,
            is_template=False,
            app=request.app,
        )

        return web.json_response({"data": data}, dumps=json_dumps)

    except JsonSchemaValidationError as exc:
        raise web.HTTPBadRequest(
            reason=f"Invalid project update: {exc.message}"
        ) from exc

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason="You do not have sufficient rights to replace the project"
        ) from exc

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound from exc


@routes.patch(f"/{VTAG}/projects/{{project_id}}", name="update_project")
@login_required
@permission_required("project.update")
@permission_required("services.pipeline.*")
async def update_project(request: web.Request):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    project_update = await parse_request_body_as(ProjectUpdate, request)

    assert db  # nosec
    assert req_ctx  # nosec
    assert path_params  # nosec
    assert project_update  # nosec

    raise NotImplementedError()


#
# - Delete https://google.aip.dev/135
#


@routes.delete(f"/{VTAG}/projects/{{project_id}}", name="delete_project")
@login_required
@permission_required("project.delete")
async def delete_project(request: web.Request):
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

    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    try:
        await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
        )
        project_users: set[int] = set()
        with managed_resource(req_ctx.user_id, None, request.app) as user_session:
            project_users = {
                us.user_id
                for us in await user_session.find_users_of_resource(
                    request.app, PROJECT_ID_KEY, f"{path_params.project_id}"
                )
            }
        # that project is still in use
        if req_ctx.user_id in project_users:
            raise web.HTTPForbidden(
                reason="Project is still open in another tab/browser."
                "It cannot be deleted until it is closed."
            )
        if project_users:
            other_user_names = {
                await get_user_name(request.app, uid) for uid in project_users
            }
            raise web.HTTPForbidden(
                reason=f"Project is open by {other_user_names}. "
                "It cannot be deleted until the project is closed."
            )

        project_locked_state: ProjectLocked | None
        if project_locked_state := await get_project_locked_state(
            app=request.app, project_uuid=path_params.project_id
        ):
            raise web.HTTPConflict(
                reason=f"Project {path_params.project_id} is locked: {project_locked_state=}"
            )

        await projects_api.submit_delete_project_task(
            request.app,
            path_params.project_id,
            req_ctx.user_id,
            request.headers.get(
                X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
            ),
        )

    except ProjectInvalidRightsError as err:
        raise web.HTTPForbidden(
            reason="You do not have sufficient rights to delete this project"
        ) from err
    except ProjectNotFoundError as err:
        raise web.HTTPNotFound(
            reason=f"Project {path_params.project_id} not found"
        ) from err
    except ProjectDeleteError as err:
        raise web.HTTPConflict(reason=f"{err}") from err

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
