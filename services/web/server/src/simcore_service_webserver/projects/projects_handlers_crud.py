""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""
import asyncio
import json
import logging
from contextlib import AsyncExitStack
from typing import Any, Coroutine, Optional

from aiohttp import web
from jsonschema import ValidationError as JsonSchemaValidationError
from models_library.projects import ProjectID
from models_library.projects_state import ProjectStatus
from models_library.rest_pagination import DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, Page
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, Extra, Field, NonNegativeInt, parse_obj_as
from servicelib.aiohttp.long_running_tasks.server import (
    TaskProgress,
    start_long_running_task,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from servicelib.utils import logged_gather
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB

from .. import catalog, director_v2_api
from .._constants import RQ_PRODUCT_KEY
from .._meta import api_version_prefix as VTAG
from ..application_settings import get_settings
from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import PROJECT_ID_KEY, managed_resource
from ..security_api import check_permission
from ..security_decorators import permission_required
from ..storage_api import (
    copy_data_folders_from_project,
    get_project_total_size_simcore_s3,
)
from ..users_api import get_user_name
from . import projects_api
from .project_models import ProjectDict, ProjectTypeAPI
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import (
    ProjectDeleteError,
    ProjectInvalidRightsError,
    ProjectNotFoundError,
)
from .projects_nodes_utils import update_frontend_outputs
from .projects_utils import (
    NodesMap,
    any_node_inputs_changed,
    clone_project_document,
    default_copy_project_name,
    get_project_unavailable_services,
    project_uses_available_services,
)

# When the user requests a project with a repo, the working copy might differ from
# the repo project. A middleware in the meta module (if active) will resolve
# the working copy and redirect to the appropriate project entrypoint. Nonetheless, the
# response needs to refer to the uuid of the request and this is passed through this request key
RQ_REQUESTED_REPO_PROJECT_UUID_KEY = f"{__name__}.RQT_REQUESTED_REPO_PROJECT_UUID_KEY"

OVERRIDABLE_DOCUMENT_KEYS = [
    "name",
    "description",
    "thumbnail",
    "prjOwner",
    "accessRights",
]
# TODO: validate these against api/specs/webserver/v0/components/schemas/project-v0.0.1.json


log = logging.getLogger(__name__)

routes = web.RouteTableDef()


class RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)


class ProjectPathParams(BaseModel):
    project_id: ProjectID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


#
# - Create https://google.aip.dev/133
#


class _ProjectCreateParams(BaseModel):
    from_study: Optional[ProjectID] = Field(
        None,
        description="Option to create a project from existing template or study: from_study={study_uuid}",
    )
    as_template: bool = Field(
        False,
        description="Option to create a template from existing project: as_template=true",
    )
    copy_data: bool = Field(
        True,
        description="Option to copy data when creating from an existing template or as a template, defaults to True",
    )
    hidden: bool = Field(
        False,
        description="Enables/disables hidden flag. Hidden projects are by default unlisted",
    )

    class Config:
        extra = Extra.forbid


@routes.post(f"/{VTAG}/projects", name="create_projects")
@login_required
@permission_required("project.create")
@permission_required("services.pipeline.*")  # due to update_pipeline_db
async def create_projects(request: web.Request):
    # get request params
    req_ctx = RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ProjectCreateParams, request)
    predefined_project = await request.json() if request.can_read_body else None
    if query_params.as_template:  # create template from
        await check_permission(request, "project.template.create")

    return await start_long_running_task(
        request,
        _create_projects,
        task_context=jsonable_encoder(req_ctx),
        app=request.app,
        request_context=req_ctx,
        query_params=query_params,
        predefined_project=predefined_project,
        fire_and_forget=True,
    )


async def _prepare_project_copy(
    app: web.Application,
    *,
    user_id: UserID,
    src_project_uuid: ProjectID,
    as_template: bool,
    deep_copy: bool,
    task_progress: TaskProgress,
) -> tuple[ProjectDict, Optional[Coroutine[Any, Any, None]]]:
    source_project = await projects_api.get_project_for_user(
        app,
        project_uuid=f"{src_project_uuid}",
        user_id=user_id,
    )
    settings = get_settings(app).WEBSERVER_PROJECTS
    assert settings  # nosec
    if max_bytes := settings.PROJECTS_MAX_COPY_SIZE_BYTES:
        # get project total data size
        project_data_size = await get_project_total_size_simcore_s3(
            app, user_id, src_project_uuid
        )
        if project_data_size >= max_bytes:
            raise web.HTTPUnprocessableEntity(
                reason=f"Source project data size is {project_data_size.human_readable()}."
                f"This is larger than the maximum {max_bytes.human_readable()} allowed for copying."
                "TIP: Please reduce the study size or contact application support."
            )

    # clone template as user project
    new_project, nodes_map = clone_project_document(
        source_project,
        forced_copy_project_id=None,
        clean_output_data=(deep_copy is False),
    )
    # remove template/study access rights
    new_project["accessRights"] = {}
    if not as_template:
        new_project["name"] = default_copy_project_name(source_project["name"])

    copy_file_coro = None
    if deep_copy and len(nodes_map) > 0:
        copy_file_coro = _copy_files_from_source_project(
            app,
            source_project,
            new_project,
            nodes_map,
            user_id,
            task_progress,
        )
    return new_project, copy_file_coro


async def _copy_files_from_source_project(
    app: web.Application,
    source_project: ProjectDict,
    new_project: ProjectDict,
    nodes_map: NodesMap,
    user_id: UserID,
    task_progress: TaskProgress,
):
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    needs_lock_source_project: bool = (
        await db.get_project_type(parse_obj_as(ProjectID, source_project["uuid"]))
        != ProjectTypeDB.TEMPLATE
    )

    async with AsyncExitStack() as stack:
        if needs_lock_source_project:
            await stack.enter_async_context(
                projects_api.lock_with_notification(
                    app,
                    source_project["uuid"],
                    ProjectStatus.CLONING,
                    user_id,
                    await get_user_name(app, user_id),
                )
            )
        starting_value = task_progress.percent
        async for long_running_task in copy_data_folders_from_project(
            app, source_project, new_project, nodes_map, user_id
        ):
            task_progress.update(
                message=long_running_task.progress.message,
                percent=(
                    starting_value
                    + long_running_task.progress.percent * (1.0 - starting_value)
                ),
            )
            if long_running_task.done():
                await long_running_task.result()


async def _create_projects(
    task_progress: TaskProgress,
    app: web.Application,
    query_params: _ProjectCreateParams,
    request_context: RequestContext,
    predefined_project: Optional[ProjectDict],
):
    """

    :raises web.HTTPBadRequest
    :raises web.HTTPNotFound
    :raises web.HTTPUnauthorized
    :raises web.HTTPCreated
    """
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    new_project = {}
    copy_file_coro = None
    try:
        task_progress.update(message="creating new study...")
        new_project_was_hidden_before_data_was_copied = query_params.hidden
        if query_params.from_study:
            # 1. prepare copy
            new_project, copy_file_coro = await _prepare_project_copy(
                app,
                user_id=request_context.user_id,
                src_project_uuid=query_params.from_study,
                as_template=query_params.as_template,
                deep_copy=query_params.copy_data,
                task_progress=task_progress,
            )

        if predefined_project:
            # 2. overrides with optional body and re-validate
            if new_project:
                for key in OVERRIDABLE_DOCUMENT_KEYS:
                    if non_null_value := predefined_project.get(key):
                        new_project[key] = non_null_value
            else:
                # TODO: take skeleton and fill instead
                new_project = predefined_project
            await projects_api.validate_project(app, new_project)

        # 3. save new project in DB
        new_project = await db.add_project(
            new_project,
            request_context.user_id,
            product_name=request_context.product_name,
            force_as_template=query_params.as_template,
            hidden=query_params.copy_data,
        )

        # 4. deep copy source project's files
        if copy_file_coro:
            # NOTE: storage needs to have access to the new project prior to copying files
            await copy_file_coro

        # 5. unhide the project if needed since it is now complete
        if not new_project_was_hidden_before_data_was_copied:
            await db.update_project_without_checking_permissions(
                new_project, new_project["uuid"], hidden=False
            )

        # update the network information in director-v2
        await director_v2_api.update_dynamic_service_networks_in_project(
            app, ProjectID(new_project["uuid"])
        )

        # This is a new project and every new graph needs to be reflected in the pipeline tables
        await director_v2_api.create_or_update_pipeline(
            app, request_context.user_id, new_project["uuid"]
        )

        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=request_context.user_id,
            project=new_project,
            is_template=query_params.as_template,
            app=app,
        )

        raise web.HTTPCreated(
            text=json_dumps({"data": new_project}),
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    except JsonSchemaValidationError as exc:
        raise web.HTTPBadRequest(reason="Invalid project data") from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {exc.project_uuid} not found") from exc
    except ProjectInvalidRightsError as exc:
        raise web.HTTPUnauthorized from exc
    except asyncio.CancelledError:
        log.warning(
            "cancelled creation of project for '%s', cleaning up",
            f"{request_context.user_id=}",
        )
        # FIXME: If cancelled during shutdown, cancellation of all_tasks will produce "new tasks"!
        if prj_uuid := new_project.get("uuid"):
            await projects_api.submit_delete_project_task(
                app, prj_uuid, request_context.user_id
            )
        raise


#
# - List https://google.aip.dev/132
#


class _ProjectListParams(BaseModel):
    limit: int = Field(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
        ge=1,
        lt=50,
    )
    offset: NonNegativeInt = Field(
        default=0, description="index to the first item to return (pagination)"
    )
    project_type: ProjectTypeAPI = Field(default=ProjectTypeAPI.all, alias="type")
    show_hidden: bool = Field(
        default=False, description="includes projects marked as hidden in the listing"
    )

    class Config:
        extra = Extra.forbid


@routes.get(f"/{VTAG}/projects", name="list_projects")
@login_required
@permission_required("project.read")
async def list_projects(request: web.Request):
    """

    :raises web.HTTPBadRequest
    """

    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]
    req_ctx = RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ProjectListParams, request)

    async def set_all_project_states(
        projects: list[dict[str, Any]], project_types: list[ProjectTypeDB]
    ):
        await logged_gather(
            *[
                projects_api.add_project_states_for_user(
                    user_id=req_ctx.user_id,
                    project=prj,
                    is_template=prj_type == ProjectTypeDB.TEMPLATE,
                    app=request.app,
                )
                for prj, prj_type in zip(projects, project_types)
            ],
            reraise=True,
            max_concurrency=100,
        )

    user_available_services: list[
        dict
    ] = await catalog.get_services_for_user_in_product(
        request.app, req_ctx.user_id, req_ctx.product_name, only_key_versions=True
    )

    projects, project_types, total_number_projects = await db.list_projects(
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        filter_by_project_type=ProjectTypeAPI.to_project_type_db(
            query_params.project_type
        ),
        filter_by_services=user_available_services,
        offset=query_params.offset,
        limit=query_params.limit,
        include_hidden=query_params.show_hidden,
    )
    await set_all_project_states(projects, project_types)
    page = Page[ProjectDict].parse_obj(
        paginate_data(
            chunk=projects,
            request_url=request.url,
            total=total_number_projects,
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
    req_ctx = RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ProjectActiveParams, request)

    try:
        project = None
        user_active_projects = []
        with managed_resource(
            req_ctx.user_id, query_params.client_session_id, request.app
        ) as rt:
            # get user's projects
            user_active_projects = await rt.find(PROJECT_ID_KEY)
        if user_active_projects:
            project = await projects_api.get_project_for_user(
                request.app,
                project_uuid=user_active_projects[0],
                user_id=req_ctx.user_id,
                include_state=True,
            )

        return web.json_response({"data": project}, dumps=json_dumps)

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason="Project not found") from exc


@routes.get(f"/{VTAG}/projects/{{project_id}}", name="get_project")
@login_required
@permission_required("project.read")
async def get_project(request: web.Request):
    """Returns all projects accessible to a user (not necesarly owned)


    :raises web.HTTPBadRequest
    """

    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    user_available_services: list[
        dict
    ] = await catalog.get_services_for_user_in_product(
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

        return web.json_response({"data": project}, dumps=json_dumps)

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
    """Implements PUT /projects

     In a PUT request, the enclosed entity is considered to be a modified version of
     the resource stored on the origin server, and the client is requesting that the
     stored version be replaced.

     With PATCH, however, the enclosed entity contains a set of instructions describing how a
     resource currently residing on the origin server should be modified to produce a new version.

     Also, another difference is that when you want to update a resource with PUT request, you have to send
     the full payload as the request whereas with PATCH, you only send the parameters which you want to update.

    :raises web.HTTPNotFound: cannot find project id in repository
    :raises web.HTTPBadRequest
    """
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    try:
        new_project = await request.json()
        # Prune state field (just in case)
        new_project.pop("state", None)

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
        await projects_api.validate_project(request.app, new_project)

        current_project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{path_params.project_id}",
            user_id=req_ctx.user_id,
            include_state=True,
        )

        if current_project["accessRights"] != new_project["accessRights"]:
            await check_permission(request, "project.access_rights.update")

        if await director_v2_api.is_pipeline_running(
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

        new_project = await db.replace_user_project(
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

        await director_v2_api.update_dynamic_service_networks_in_project(
            request.app, path_params.project_id
        )
        await director_v2_api.create_or_update_pipeline(
            request.app, req_ctx.user_id, path_params.project_id
        )
        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=req_ctx.user_id,
            project=new_project,
            is_template=False,
            app=request.app,
        )

    except JsonSchemaValidationError as exc:
        raise web.HTTPBadRequest(
            reason=f"Invalid project update: {exc.message}"
        ) from exc

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason="You do not have sufficient rights to save the project"
        ) from exc

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound from exc

    return web.json_response({"data": new_project}, dumps=json_dumps)


#
# - Delete https://google.aip.dev/135
#


@routes.delete(f"/{VTAG}/projects/{{project_id}}", name="delete_project")
@login_required
@permission_required("project.delete")
async def delete_project(request: web.Request):
    """

    :raises web.HTTPNotFound
    :raises web.HTTPBadRequest
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
        with managed_resource(req_ctx.user_id, None, request.app) as rt:
            project_users = {
                user_session.user_id
                for user_session in await rt.find_users_of_resource(
                    PROJECT_ID_KEY, f"{path_params.project_id}"
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

        await projects_api.submit_delete_project_task(
            request.app, path_params.project_id, req_ctx.user_id
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
