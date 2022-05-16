""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""
import asyncio
import json
import logging
from typing import Any, Coroutine, Dict, List, Optional, Set
from uuid import UUID

from aiohttp import web
from jsonschema import ValidationError as JsonSchemaValidationError
from models_library.basic_types import UUIDStr
from models_library.projects_state import ProjectStatus
from models_library.rest_pagination import Page, PageMetaInfoLimitOffset
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.json_serialization import json_dumps
from servicelib.mime import APPLICATION_JSON
from servicelib.utils import logged_gather
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB

from .. import catalog, director_v2_api
from .._constants import RQ_PRODUCT_KEY
from .._meta import api_version_prefix as VTAG
from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import PROJECT_ID_KEY, managed_resource
from ..rest_constants import RESPONSE_MODEL_POLICY
from ..security_api import check_permission
from ..security_decorators import permission_required
from ..storage_api import copy_data_folders_from_project
from ..users_api import get_user_name
from . import projects_api
from .project_models import ProjectDict, ProjectTypeAPI
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from .projects_utils import (
    any_node_inputs_changed,
    clone_project_document,
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


class BaseRequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)


class ProjectPathParams(BaseModel):
    project_uuid: UUID = Field(..., alias="project_id")

    class Config:
        allow_population_by_field_name = True


#
# - Create https://google.aip.dev/133
#


class _ProjectCreateParams(BaseModel):
    template_uuid: Optional[UUIDStr] = None
    as_template: Optional[UUIDStr] = None
    copy_data: bool = True
    hidden: bool = False


@routes.post(f"/{VTAG}/projects")
@login_required
@permission_required("project.create")
@permission_required("services.pipeline.*")  # due to update_pipeline_db
async def create_projects(request: web.Request):
    """

    :raises web.HTTPBadRequest
    :raises web.HTTPNotFound
    :raises web.HTTPBadRequest
    :raises web.HTTPNotFound
    :raises web.HTTPUnauthorized
    :raises web.HTTPCreated
    """
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements

    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]
    c = BaseRequestContext.parse_obj(request)
    q = parse_request_query_parameters_as(_ProjectCreateParams, request)

    new_project = {}
    try:
        new_project_was_hidden_before_data_was_copied = q.hidden

        clone_data_coro: Optional[Coroutine] = None
        source_project: Optional[ProjectDict] = None
        if q.as_template:  # create template from
            await check_permission(request, "project.template.create")
            source_project = await projects_api.get_project_for_user(
                request.app,
                project_uuid=q.as_template,
                user_id=c.user_id,
                include_templates=False,
            )
        elif q.template_uuid:  # create from template
            source_project = await db.get_template_project(q.template_uuid)
            if not source_project:
                raise web.HTTPNotFound(
                    reason="Invalid template uuid {}".format(q.template_uuid)
                )

        if source_project:
            # clone template as user project
            new_project, nodes_map = clone_project_document(
                source_project,
                forced_copy_project_id=None,
                clean_output_data=(q.copy_data == False),
            )
            if q.template_uuid:
                # remove template access rights
                new_project["accessRights"] = {}
            # the project is to be hidden until the data is copied
            q.hidden = q.copy_data
            clone_data_coro = (
                copy_data_folders_from_project(
                    request.app, source_project, new_project, nodes_map, c.user_id
                )
                if q.copy_data
                else None
            )
            # FIXME: parameterized inputs should get defaults provided by service

        # overrides with body
        if request.can_read_body:
            predefined = await request.json()
            if new_project:
                for key in OVERRIDABLE_DOCUMENT_KEYS:
                    non_null_value = predefined.get(key)
                    if non_null_value:
                        new_project[key] = non_null_value
            else:
                # TODO: take skeleton and fill instead
                new_project = predefined

        # re-validate data
        await projects_api.validate_project(request.app, new_project)

        # update metadata (uuid, timestamps, ownership) and save
        new_project = await db.add_project(
            new_project,
            c.user_id,
            force_as_template=q.as_template is not None,
            hidden=q.hidden,
        )

        # copies the project's DATA IF cloned
        if clone_data_coro:
            assert source_project  # nosec
            if q.as_template:
                # we need to lock the original study while copying the data
                async with projects_api.lock_with_notification(
                    request.app,
                    source_project["uuid"],
                    ProjectStatus.CLONING,
                    c.user_id,
                    await get_user_name(request.app, c.user_id),
                ):

                    await clone_data_coro
            else:
                await clone_data_coro
            # unhide the project if needed since it is now complete
            if not new_project_was_hidden_before_data_was_copied:
                await db.update_project_without_checking_permissions(
                    new_project, new_project["uuid"], hidden=False
                )

        await director_v2_api.projects_networks_update(
            request.app, UUID(new_project["uuid"])
        )

        # This is a new project and every new graph needs to be reflected in the pipeline tables
        await director_v2_api.create_or_update_pipeline(
            request.app, c.user_id, new_project["uuid"]
        )

        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=c.user_id,
            project=new_project,
            is_template=q.as_template is not None,
            app=request.app,
        )

    except JsonSchemaValidationError as exc:
        raise web.HTTPBadRequest(reason="Invalid project data") from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason="Project not found") from exc
    except ProjectInvalidRightsError as exc:
        raise web.HTTPUnauthorized from exc
    except asyncio.CancelledError:
        log.warning(
            "cancelled creation of project for user '%s', cleaning up", f"{c.user_id=}"
        )
        await projects_api.submit_delete_project_task(
            request.app, new_project["uuid"], c.user_id
        )
        raise
    else:
        log.debug("project created successfuly")
        raise web.HTTPCreated(
            text=json.dumps(new_project), content_type=APPLICATION_JSON
        )


#
# - List https://google.aip.dev/132
#


class _ProjectListParams(PageMetaInfoLimitOffset):
    project_type: ProjectTypeAPI = Field(ProjectTypeAPI.all, alias="type")
    show_hidden: bool


@routes.get(f"/{VTAG}/projects")
@login_required
@permission_required("project.read")
async def list_projects(request: web.Request):
    """

    :raises web.HTTPBadRequest
    """

    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]
    c = BaseRequestContext.parse_obj(request)
    q = parse_request_query_parameters_as(_ProjectListParams, request)

    async def set_all_project_states(
        projects: List[Dict[str, Any]], project_types: List[ProjectTypeDB]
    ):
        await logged_gather(
            *[
                projects_api.add_project_states_for_user(
                    user_id=c.user_id,
                    project=prj,
                    is_template=prj_type == ProjectTypeDB.TEMPLATE,
                    app=request.app,
                )
                for prj, prj_type in zip(projects, project_types)
            ],
            reraise=True,
            max_concurrency=100,
        )

    user_available_services: List[
        Dict
    ] = await catalog.get_services_for_user_in_product(
        request.app, c.user_id, c.product_name, only_key_versions=True
    )

    projects, project_types, total_number_projects = await db.load_projects(
        user_id=c.user_id,
        filter_by_project_type=ProjectTypeAPI.to_project_type_db(q.project_type),
        filter_by_services=user_available_services,
        offset=q.offset,
        limit=q.limit,
        include_hidden=q.show_hidden,
    )
    await set_all_project_states(projects, project_types)
    page = Page[ProjectDict].parse_obj(
        paginate_data(
            chunk=projects,
            request_url=request.url,
            total=total_number_projects,
            limit=q.limit,
            offset=q.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type=APPLICATION_JSON,
    )


#
# - Get https://google.aip.dev/131
#


@routes.get(f"/{VTAG}/projects/{{project_uuid}}")
@login_required
@permission_required("project.read")
async def get_project(request: web.Request):
    """Returns all projects accessible to a user (not necesarly owned)


    :raises web.HTTPBadRequest
    """

    c = BaseRequestContext.parse_obj(request)
    p = parse_request_path_parameters_as(ProjectPathParams, request)

    user_available_services: List[
        Dict
    ] = await catalog.get_services_for_user_in_product(
        request.app, c.user_id, c.product_name, only_key_versions=True
    )

    try:
        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=p.project_uuid,
            user_id=c.user_id,
            include_templates=True,
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
                    f"Project '{p.project_uuid}' uses unavailable services. Please ask "
                    f"for permission for the following services {formatted_services}"
                )
            )

        if new_uuid := request.get(RQ_REQUESTED_REPO_PROJECT_UUID_KEY):
            project["uuid"] = new_uuid

        return web.json_response({"data": project}, dumps=json_dumps)

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason=f"You do not have sufficient rights to read project {p.project_uuid}"
        ) from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {p.project_uuid} not found") from exc


#
# - Update https://google.aip.dev/134
#


@routes.put(f"/{VTAG}/projects/{{project_uuid}}")
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
    c = BaseRequestContext.parse_obj(request)
    p = parse_request_path_parameters_as(ProjectPathParams, request)

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
            "project_id": f"{p.project_uuid}",
            "user_id": c.user_id,
            "new_data": new_project,
        },
    )

    try:
        await projects_api.validate_project(request.app, new_project)

        current_project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{p.project_uuid}",
            user_id=c.user_id,
            include_templates=True,
            include_state=True,
        )

        if current_project["accessRights"] != new_project["accessRights"]:
            await check_permission(request, "project.access_rights.update")

        if await director_v2_api.is_pipeline_running(
            request.app, c.user_id, p.project_uuid
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
                    reason=f"Project {p.project_uuid} cannot be modified while pipeline is still running."
                )

        new_project = await db.replace_user_project(
            new_project, c.user_id, f"{p.project_uuid}", include_templates=True
        )
        await director_v2_api.projects_networks_update(request.app, p.project_uuid)
        await director_v2_api.create_or_update_pipeline(
            request.app, c.user_id, p.project_uuid
        )
        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=c.user_id,
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


@routes.delete(f"/{VTAG}/projects/{{project_uuid}}")
@login_required
@permission_required("project.delete")
async def delete_project(request: web.Request):
    """

    : raises web.HTTPNotFound
    :raises web.HTTPBadRequest
    """
    c = BaseRequestContext.parse_obj(request)
    p = parse_request_path_parameters_as(ProjectPathParams, request)

    try:
        await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{p.project_uuid}",
            user_id=c.user_id,
            include_templates=True,
        )
        project_users: Set[int] = set()
        with managed_resource(c.user_id, None, request.app) as rt:
            project_users = {
                user_session.user_id
                for user_session in await rt.find_users_of_resource(
                    PROJECT_ID_KEY, f"{p.project_uuid}"
                )
            }
        # that project is still in use
        if c.user_id in project_users:
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
            request.app, p.project_uuid, c.user_id
        )

    except ProjectInvalidRightsError as err:
        raise web.HTTPForbidden(
            reason="You do not have sufficient rights to delete this project"
        ) from err
    except ProjectNotFoundError as err:
        raise web.HTTPNotFound(reason=f"Project {p.project_uuid} not found") from err

    raise web.HTTPNoContent(content_type=APPLICATION_JSON)
