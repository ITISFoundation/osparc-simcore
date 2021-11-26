""" Handlers for CRUD operations on /projects/

"""

import asyncio
import json
import logging
from typing import Any, Coroutine, Dict, List, Optional, Set

from aiohttp import web
from jsonschema import ValidationError
from models_library.projects import ProjectID
from models_library.projects_state import ProjectState, ProjectStatus
from servicelib.json_serialization import json_dumps
from servicelib.rest_pagination_utils import PageResponseLimitOffset
from servicelib.utils import logged_gather
from simcore_postgres_database.webserver_models import ProjectType as ProjectTypeDB

from .. import catalog, director_v2_api
from .._meta import api_version_prefix as VTAG
from ..constants import RQ_PRODUCT_KEY
from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import PROJECT_ID_KEY, managed_resource
from ..rest_utils import RESPONSE_MODEL_POLICY
from ..security_api import check_permission
from ..security_decorators import permission_required
from ..storage_api import copy_data_folders_from_project
from ..users_api import get_user_name
from . import projects_api
from .project_models import ProjectTypeAPI
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from .projects_utils import (
    clone_project_document,
    get_project_unavailable_services,
    project_uses_available_services,
)

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


@routes.post(f"/{VTAG}/projects")
@login_required
@permission_required("project.create")
@permission_required("services.pipeline.*")  # due to update_pipeline_db
async def create_projects(
    request: web.Request,
):  # pylint: disable=too-many-branches, too-many-statements
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]
    template_uuid = request.query.get("from_template")
    as_template = request.query.get("as_template")
    copy_data: bool = bool(
        request.query.get("copy_data", "true") in [1, "true", "True"]
    )
    hidden: bool = bool(request.query.get("hidden", False))

    new_project = {}
    new_project_was_hidden_before_data_was_copied = hidden
    try:
        clone_data_coro: Optional[Coroutine] = None
        source_project: Optional[Dict[str, Any]] = None
        if as_template:  # create template from
            await check_permission(request, "project.template.create")
            source_project = await projects_api.get_project_for_user(
                request.app,
                project_uuid=as_template,
                user_id=user_id,
                include_templates=False,
            )
        elif template_uuid:  # create from template
            source_project = await db.get_template_project(template_uuid)
            if not source_project:
                raise web.HTTPNotFound(
                    reason="Invalid template uuid {}".format(template_uuid)
                )
        if source_project:
            # clone template as user project
            new_project, nodes_map = clone_project_document(
                source_project,
                forced_copy_project_id=None,
                clean_output_data=(copy_data == False),
            )
            if template_uuid:
                # remove template access rights
                new_project["accessRights"] = {}
            # the project is to be hidden until the data is copied
            hidden = copy_data
            clone_data_coro = (
                copy_data_folders_from_project(
                    request.app, source_project, new_project, nodes_map, user_id
                )
                if copy_data
                else None
            )
            # FIXME: parameterized inputs should get defaults provided by service

        # overrides with body
        if request.has_body:
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
            user_id,
            force_as_template=as_template is not None,
            hidden=hidden,
        )

        # copies the project's DATA IF cloned
        if clone_data_coro:
            assert source_project  # nosec
            if as_template:
                # we need to lock the original study while copying the data
                async with projects_api.lock_with_notification(
                    request.app,
                    source_project["uuid"],
                    ProjectStatus.CLONING,
                    user_id,
                    await get_user_name(request.app, user_id),
                ):

                    await clone_data_coro
            else:
                await clone_data_coro
            # unhide the project if needed since it is now complete
            if not new_project_was_hidden_before_data_was_copied:
                await db.update_project_without_checking_permissions(
                    new_project, new_project["uuid"], hidden=False
                )

        # This is a new project and every new graph needs to be reflected in the pipeline tables
        await director_v2_api.create_or_update_pipeline(
            request.app, user_id, new_project["uuid"]
        )

        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=user_id,
            project=new_project,
            is_template=as_template is not None,
            app=request.app,
        )

    except ValidationError as exc:
        raise web.HTTPBadRequest(reason="Invalid project data") from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason="Project not found") from exc
    except ProjectInvalidRightsError as exc:
        raise web.HTTPUnauthorized from exc
    except asyncio.CancelledError:
        log.warning(
            "cancelled creation of project for user '%s', cleaning up", f"{user_id=}"
        )
        await projects_api.delete_project(request.app, new_project["uuid"], user_id)
        raise
    else:
        log.debug("project created successfuly")
        raise web.HTTPCreated(
            text=json.dumps(new_project), content_type="application/json"
        )


@routes.get(f"/{VTAG}/projects")
@login_required
@permission_required("project.read")
async def list_projects(request: web.Request):
    # TODO: implement all query parameters as
    # in https://www.ibm.com/support/knowledgecenter/en/SSCRJU_3.2.0/com.ibm.swg.im.infosphere.streams.rest.api.doc/doc/restapis-queryparms-list.html
    from servicelib.aiohttp.rest_utils import extract_and_validate

    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]
    _, query, _ = await extract_and_validate(request)

    project_type = ProjectTypeAPI(query["type"])
    offset = query["offset"]
    limit = query["limit"]
    show_hidden = query["show_hidden"]

    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    async def set_all_project_states(
        projects: List[Dict[str, Any]], project_types: List[bool]
    ):
        await logged_gather(
            *[
                projects_api.add_project_states_for_user(
                    user_id=user_id,
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
        request.app, user_id, product_name, only_key_versions=True
    )

    projects, project_types, total_number_projects = await db.load_projects(
        user_id=user_id,
        filter_by_project_type=ProjectTypeAPI.to_project_type_db(project_type),
        filter_by_services=user_available_services,
        offset=offset,
        limit=limit,
        include_hidden=show_hidden,
    )
    await set_all_project_states(projects, project_types)
    return PageResponseLimitOffset.paginate_data(
        data=projects,
        request_url=request.url,
        total=total_number_projects,
        limit=limit,
        offset=offset,
    ).dict(**RESPONSE_MODEL_POLICY)


@routes.get(f"/{VTAG}/projects/{{project_uuid}}")
@login_required
@permission_required("project.read")
async def get_project(request: web.Request):
    """Returns all projects accessible to a user (not necesarly owned)"""
    # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]
    try:
        project_uuid = request.match_info["project_id"]
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    user_available_services: List[
        Dict
    ] = await catalog.get_services_for_user_in_product(
        request.app, user_id, product_name, only_key_versions=True
    )

    try:
        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
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
            raise web.HTTPNotFound(
                reason=(
                    f"Project '{project_uuid}' uses unavailable services. Please ask "
                    f"for permission for the following services {formatted_services}"
                )
            )
        return {"data": project}

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason=f"You do not have sufficient rights to read project {project_uuid}"
        ) from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


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
    """
    user_id: int = request[RQT_USERID_KEY]
    try:
        project_uuid = ProjectID(request.match_info["project_id"])
        new_project = await request.json()

    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason="Invalid request body") from exc

    # Prune state field (just in case)
    new_project.pop("state", None)

    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]
    await check_permission(
        request,
        "project.update | project.workbench.node.inputs.update",
        context={
            "dbapi": db,
            "project_id": f"{project_uuid}",
            "user_id": user_id,
            "new_data": new_project,
        },
    )

    try:
        await projects_api.validate_project(request.app, new_project)

        current_project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=f"{project_uuid}",
            user_id=user_id,
            include_templates=True,
            include_state=True,
        )

        if current_project["accessRights"] != new_project["accessRights"]:
            await check_permission(request, "project.access_rights.update")

        new_project = await db.replace_user_project(
            new_project, user_id, f"{project_uuid}", include_templates=True
        )
        await director_v2_api.create_or_update_pipeline(
            request.app, user_id, project_uuid
        )
        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=user_id,
            project=new_project,
            is_template=False,
            app=request.app,
        )

    except ValidationError as exc:
        raise web.HTTPBadRequest(
            reason=f"Invalid project update: {exc.message}"
        ) from exc

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason="You do not have sufficient rights to save the project"
        ) from exc

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound from exc

    return {"data": new_project}


@routes.delete(f"/{VTAG}/projects/{{project_uuid}}")
@login_required
@permission_required("project.delete")
async def delete_project(request: web.Request):
    # first check if the project exists
    user_id: int = request[RQT_USERID_KEY]
    try:
        project_uuid = request.match_info["project_id"]
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    try:
        await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )
        project_users: Set[int] = set()
        with managed_resource(user_id, None, request.app) as rt:
            project_users = {
                user_session.user_id
                for user_session in await rt.find_users_of_resource(
                    PROJECT_ID_KEY, project_uuid
                )
            }
        # that project is still in use
        if user_id in project_users:
            raise web.HTTPForbidden(
                reason="Project is still open in another tab/browser. It cannot be deleted until it is closed."
            )
        if project_users:
            other_user_names = {
                await get_user_name(request.app, x) for x in project_users
            }
            raise web.HTTPForbidden(
                reason=f"Project is open by {other_user_names}. It cannot be deleted until the project is closed."
            )

        await projects_api.delete_project(request.app, project_uuid, user_id)
    except ProjectInvalidRightsError as err:
        raise web.HTTPForbidden(
            reason="You do not have sufficient rights to delete this project"
        ) from err
    except ProjectNotFoundError as err:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from err

    raise web.HTTPNoContent(content_type="application/json")


class HTTPLocked(web.HTTPClientError):
    # pylint: disable=too-many-ancestors
    status_code = 423


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
