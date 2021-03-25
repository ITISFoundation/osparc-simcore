""" Handlers for CRUD operations on /projects/

"""
import json
import logging
from typing import Any, Coroutine, Dict, List, Optional, Set

import aioredlock
from aiohttp import web
from jsonschema import ValidationError
from models_library.projects_state import ProjectState
from servicelib.utils import fire_and_forget_task, logged_gather

from .. import catalog, director_v2
from ..constants import RQ_PRODUCT_KEY
from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import managed_resource
from ..security_api import check_permission
from ..security_decorators import permission_required
from ..storage_api import copy_data_folders_from_project
from ..users_api import get_user_name
from . import projects_api
from .projects_db import APP_PROJECT_DBAPI
from .projects_exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from .projects_utils import clone_project_document, project_uses_available_services

OVERRIDABLE_DOCUMENT_KEYS = [
    "name",
    "description",
    "thumbnail",
    "prjOwner",
    "accessRights",
]
# TODO: validate these against api/specs/webserver/v0/components/schemas/project-v0.0.1.json

log = logging.getLogger(__name__)


@login_required
@permission_required("project.create")
@permission_required("services.pipeline.*")  # due to update_pipeline_db
async def create_projects(request: web.Request):
    # pylint: disable=too-many-branches
    # TODO: keep here since is async and parser thinks it is a handler

    user_id = request[RQT_USERID_KEY]
    db = request.config_dict[APP_PROJECT_DBAPI]

    template_uuid = request.query.get("from_template")
    as_template = request.query.get("as_template")

    try:
        project = {}
        clone_data_coro: Optional[Coroutine] = None

        if as_template:  # create template from
            await check_permission(request, "project.template.create")

            source_project = await projects_api.get_project_for_user(
                request.app,
                project_uuid=as_template,
                user_id=user_id,
                include_templates=False,
            )
            # clone user project as tempalte
            project, nodes_map = clone_project_document(
                source_project, forced_copy_project_id=False
            )
            clone_data_coro = copy_data_folders_from_project(
                request.app, source_project, project, nodes_map, user_id
            )

        elif template_uuid:  # create from template
            source_project = await db.get_template_project(template_uuid)
            if not source_project:
                raise web.HTTPNotFound(
                    reason="Invalid template uuid {}".format(template_uuid)
                )
            # clone template as user project
            project, nodes_map = clone_project_document(
                source_project, forced_copy_project_id=False
            )
            clone_data_coro = copy_data_folders_from_project(
                request.app, source_project, project, nodes_map, user_id
            )

            # remove template access rights
            project["accessRights"] = {}
            # FIXME: parameterized inputs should get defaults provided by service

        # overrides with body
        if request.has_body:
            predefined = await request.json()
            if project:
                for key in OVERRIDABLE_DOCUMENT_KEYS:
                    non_null_value = predefined.get(key)
                    if non_null_value:
                        project[key] = non_null_value
            else:
                # TODO: take skeleton and fill instead
                project = predefined

        # re-validate data
        projects_api.validate_project(request.app, project)

        # update metadata (uuid, timestamps, ownership) and save
        project = await db.add_project(
            project, user_id, force_as_template=as_template is not None
        )

        # copies the project's DATA IF cloned
        if clone_data_coro:
            await clone_data_coro

        # This is a new project and every new graph needs to be reflected in the pipeline tables
        await director_v2.create_or_update_pipeline(
            request.app, user_id, project["uuid"]
        )

        # Appends state
        project = await projects_api.add_project_states_for_user(
            user_id=user_id,
            project=project,
            is_template=as_template is not None,
            app=request.app,
        )

    except ValidationError as exc:
        raise web.HTTPBadRequest(reason="Invalid project data") from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason="Project not found") from exc
    except ProjectInvalidRightsError as exc:
        raise web.HTTPUnauthorized from exc

    else:
        raise web.HTTPCreated(text=json.dumps(project), content_type="application/json")


@login_required
@permission_required("project.read")
async def list_projects(request: web.Request):
    # TODO: implement all query parameters as
    # in https://www.ibm.com/support/knowledgecenter/en/SSCRJU_3.2.0/com.ibm.swg.im.infosphere.streams.rest.api.doc/doc/restapis-queryparms-list.html

    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]
    ptype = request.query.get("type", "all")  # TODO: get default for oaspecs
    db = request.config_dict[APP_PROJECT_DBAPI]

    # TODO: improve dbapi to list project
    async def set_all_project_states(projects: List[Dict[str, Any]], is_template: bool):
        await logged_gather(
            *[
                projects_api.add_project_states_for_user(
                    user_id=user_id,
                    project=prj,
                    is_template=is_template,
                    app=request.app,
                )
                for prj in projects
            ],
            reraise=True,
        )

    user_available_services: List[
        Dict
    ] = await catalog.get_services_for_user_in_product(
        request.app, user_id, product_name, only_key_versions=True
    )

    projects_list = []
    if ptype in ("template", "all"):
        template_projects = await db.load_template_projects(
            user_id=user_id, filter_by_services=user_available_services
        )
        await set_all_project_states(template_projects, is_template=True)
        projects_list += template_projects

    if ptype in ("user", "all"):  # standard only (notice that templates will only)
        user_projects = await db.load_user_projects(
            user_id=user_id, filter_by_services=user_available_services
        )
        await set_all_project_states(user_projects, is_template=False)
        projects_list += user_projects

    start = int(request.query.get("start", 0))
    count = int(request.query.get("count", len(projects_list)))

    stop = min(start + count, len(projects_list))
    projects_list = projects_list[start:stop]
    return {"data": projects_list}


@login_required
@permission_required("project.read")
async def get_project(request: web.Request):
    """Returns all projects accessible to a user (not necesarly owned)"""
    # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]
    user_available_services: List[
        Dict
    ] = await catalog.get_services_for_user_in_product(
        request.app, user_id, product_name, only_key_versions=True
    )
    project_uuid = request.match_info.get("project_id")
    try:
        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
            include_state=True,
        )
        if not await project_uses_available_services(project, user_available_services):
            raise web.HTTPNotFound(
                reason=f"Project '{project_uuid}' uses unavailable services. Please ask your administrator."
            )
        return {"data": project}

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason=f"You do not have sufficient rights to read project {project_uuid}"
        ) from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


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
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    new_project = await request.json()

    # Prune state field (just in case)
    new_project.pop("state", None)

    db = request.config_dict[APP_PROJECT_DBAPI]
    await check_permission(
        request,
        "project.update | project.workbench.node.inputs.update",
        context={
            "dbapi": db,
            "project_id": project_uuid,
            "user_id": user_id,
            "new_data": new_project,
        },
    )

    try:
        projects_api.validate_project(request.app, new_project)

        current_project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
            include_state=True,
        )

        if current_project["accessRights"] != new_project["accessRights"]:
            await check_permission(request, "project.access_rights.update")

        new_project = await db.replace_user_project(
            new_project, user_id, project_uuid, include_templates=True
        )
        await director_v2.create_or_update_pipeline(request.app, user_id, project_uuid)
        # Appends state
        new_project = await projects_api.add_project_states_for_user(
            user_id=user_id,
            project=new_project,
            is_template=False,
            app=request.app,
        )

    except ValidationError as exc:
        raise web.HTTPBadRequest from exc

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason="You do not have sufficient rights to save the project"
        ) from exc

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound from exc

    return {"data": new_project}


@login_required
@permission_required("project.delete")
async def delete_project(request: web.Request):
    # first check if the project exists
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    try:
        await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )
        project_users: Set[int] = {}
        with managed_resource(user_id, None, request.app) as rt:
            project_users = set(
                await rt.find_users_of_resource("project_id", project_uuid)
            )
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


@login_required
@permission_required("project.open")
async def open_project(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    client_session_id = await request.json()
    try:
        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
            include_state=True,
        )

        async def try_add_project() -> Optional[Set[int]]:
            with managed_resource(user_id, client_session_id, request.app) as rt:
                try:
                    async with await rt.get_registry_lock():
                        other_users: Set[int] = set(
                            await rt.find_users_of_resource("project_id", project_uuid)
                        )
                        if user_id in other_users:
                            other_users.remove(user_id)
                        if other_users:
                            return other_users
                        await rt.add("project_id", project_uuid)
                except aioredlock.LockError as exc:
                    # TODO: this lock is not a good solution for long term
                    # maybe a project key in redis might improve spped of checking
                    raise HTTPLocked(reason="Project is locked") from exc

        other_users = await try_add_project()
        if other_users:
            # project is already locked
            usernames = [
                await projects_api.get_user_name(request.app, uid)
                for uid in other_users
            ]
            raise HTTPLocked(reason=f"Project is already opened by {usernames}")

        # user id opened project uuid
        await projects_api.start_project_interactive_services(request, project, user_id)

        # notify users that project is now locked
        project = await projects_api.add_project_states_for_user(
            user_id=user_id,
            project=project,
            is_template=False,
            app=request.app,
        )

        await projects_api.notify_project_state_update(request.app, project)

        return web.json_response({"data": project})

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


@login_required
@permission_required("project.close")
async def close_project(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    client_session_id = await request.json()

    try:
        # ensure the project exists
        project = await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
            include_state=False,
        )
        # if we are the only user left we can safely remove the services
        async def _close_project_task(project: Dict[str, Any]) -> None:
            try:
                project_opened_by_others: bool = False
                with managed_resource(user_id, client_session_id, request.app) as rt:
                    project_users: List[int] = await rt.find_users_of_resource(
                        "project_id", project_uuid
                    )
                    project_opened_by_others = len(project_users) > 1

                if not project_opened_by_others:
                    # only remove the services if no one else is using them now
                    await projects_api.remove_project_interactive_services(
                        user_id, project_uuid, request.app
                    )
            finally:
                with managed_resource(user_id, client_session_id, request.app) as rt:
                    # now we can remove the lock
                    await rt.remove("project_id")
                # ensure we notify the user whatever happens, the GC should take care of dangling services in case of issue
                project = await projects_api.add_project_states_for_user(
                    user_id=user_id,
                    project=project,
                    is_template=False,
                    app=request.app,
                )
                await projects_api.notify_project_state_update(request.app, project)

        fire_and_forget_task(_close_project_task(project))

        raise web.HTTPNoContent(content_type="application/json")
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


@login_required
@permission_required("project.read")
async def state_project(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")

    # check that project exists and queries state
    validated_project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=project_uuid,
        user_id=user_id,
        include_templates=True,
        include_state=True,
    )
    project_state = ProjectState(**validated_project["state"])
    return web.json_response({"data": project_state.dict()})


@login_required
@permission_required("project.read")
async def get_active_project(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    client_session_id = request.query["client_session_id"]

    try:
        project = None
        user_active_projects = []
        with managed_resource(user_id, client_session_id, request.app) as rt:
            # get user's projects
            user_active_projects = await rt.find("project_id")
        if user_active_projects:

            project = await projects_api.get_project_for_user(
                request.app,
                project_uuid=user_active_projects[0],
                user_id=user_id,
                include_templates=True,
                include_state=True,
            )

        return web.json_response({"data": project})

    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason="Project not found") from exc


@login_required
@permission_required("project.node.create")
async def create_node(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    body = await request.json()

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
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    node_uuid = request.match_info.get("node_id")
    try:
        # ensure the project exists

        await projects_api.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )

        node_details = await projects_api.get_project_node(
            request, project_uuid, user_id, node_uuid
        )
        return web.json_response({"data": node_details})
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


@login_required
@permission_required("project.node.delete")
async def delete_node(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    node_uuid = request.match_info.get("node_id")
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
    uid, db = request[RQT_USERID_KEY], request.config_dict[APP_PROJECT_DBAPI]
    tag_id, study_uuid = (
        request.match_info.get("tag_id"),
        request.match_info.get("study_uuid"),
    )
    return await db.add_tag(project_uuid=study_uuid, user_id=uid, tag_id=int(tag_id))


@login_required
@permission_required("project.tag.*")
async def remove_tag(request: web.Request):
    uid, db = request[RQT_USERID_KEY], request.config_dict[APP_PROJECT_DBAPI]
    tag_id, study_uuid = (
        request.match_info.get("tag_id"),
        request.match_info.get("study_uuid"),
    )
    return await db.remove_tag(project_uuid=study_uuid, user_id=uid, tag_id=int(tag_id))
