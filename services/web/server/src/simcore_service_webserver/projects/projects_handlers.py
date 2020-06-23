""" Handlers for CRUD operations on /projects/

"""
import json
import logging

from aiohttp import web
from jsonschema import ValidationError

from servicelib.utils import fire_and_forget_task

from ..computation_api import update_pipeline_db
from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import managed_resource
from ..security_api import check_permission
from ..security_decorators import permission_required
from . import projects_api
from .projects_db import APP_PROJECT_DBAPI
from .projects_exceptions import ProjectInvalidRightsError, ProjectNotFoundError

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
    from .projects_api import (
        clone_project,
    )  # TODO: keep here since is async and parser thinks it is a handler

    # pylint: disable=too-many-branches

    user_id = request[RQT_USERID_KEY]
    db = request.config_dict[APP_PROJECT_DBAPI]

    template_uuid = request.query.get("from_template")
    as_template = request.query.get("as_template")

    try:
        project = {}
        if as_template:  # create template from
            await check_permission(request, "project.template.create")

            # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
            from .projects_api import get_project_for_user

            source_project = await get_project_for_user(
                request.app,
                project_uuid=as_template,
                user_id=user_id,
                include_templates=False,
            )
            project = await clone_project(request, source_project, user_id)

        elif template_uuid:  # create from template
            template_prj = await db.get_template_project(template_uuid)
            if not template_prj:
                raise web.HTTPNotFound(
                    reason="Invalid template uuid {}".format(template_uuid)
                )

            project = await clone_project(request, template_prj, user_id)
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

        # validate data
        projects_api.validate_project(request.app, project)

        # update metadata (uuid, timestamps, ownership) and save
        project = await db.add_project(
            project, user_id, force_as_template=as_template is not None
        )

        # This is a new project and every new graph needs to be reflected in the pipeline db
        await update_pipeline_db(request.app, project["uuid"], project["workbench"])

    except ValidationError:
        raise web.HTTPBadRequest(reason="Invalid project data")
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason="Project not found")
    except ProjectInvalidRightsError:
        raise web.HTTPUnauthorized

    else:
        raise web.HTTPCreated(text=json.dumps(project), content_type="application/json")


@login_required
@permission_required("project.read")
async def list_projects(request: web.Request):

    # TODO: implement all query parameters as
    # in https://www.ibm.com/support/knowledgecenter/en/SSCRJU_3.2.0/com.ibm.swg.im.infosphere.streams.rest.api.doc/doc/restapis-queryparms-list.html
    user_id = request[RQT_USERID_KEY]
    ptype = request.query.get("type", "all")  # TODO: get default for oaspecs
    db = request.config_dict[APP_PROJECT_DBAPI]

    # TODO: improve dbapi to list project
    projects_list = []
    if ptype in ("template", "all"):
        projects_list += await db.load_template_projects(user_id=user_id)

    if ptype in ("user", "all"):  # standard only (notice that templates will only)
        projects_list += await db.load_user_projects(user_id=user_id)

    start = int(request.query.get("start", 0))
    count = int(request.query.get("count", len(projects_list)))

    stop = min(start + count, len(projects_list))
    projects_list = projects_list[start:stop]

    # validate response
    validated_projects = []
    for project in projects_list:
        try:
            projects_api.validate_project(request.app, project)
            validated_projects.append(project)
        except ValidationError:
            log.exception("Skipping invalid project from list")
            continue

    return {"data": validated_projects}


@login_required
@permission_required("project.read")
async def get_project(request: web.Request):
    """ Returns all projects accessible to a user (not necesarly owned)

    """
    # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
    user_id = request[RQT_USERID_KEY]
    from .projects_api import get_project_for_user

    project_uuid = request.match_info.get("project_id")
    try:
        project = await get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=request[RQT_USERID_KEY],
            include_templates=True,
        )

        return {"data": project}
    except ProjectInvalidRightsError:
        raise web.HTTPForbidden(
            reason=f"User {user_id} has no right to read {project_uuid}"
        )
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found")


@login_required
@permission_required("services.pipeline.*")  # due to update_pipeline_db
async def replace_project(request: web.Request):
    """ Implements PUT /projects

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
    replace_pipeline = request.query.get(
        "run", False
    )  # FIXME: Actually was never called. CHECK if logic still applies (issue #1176)
    new_project = await request.json()

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
        # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
        from .projects_api import get_project_for_user

        projects_api.validate_project(request.app, new_project)
        current_project = await get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=False,
        )
        if current_project["accessRights"] != new_project["accessRights"]:
            await check_permission(request, "project.access_rights.update")
        new_project = await db.update_user_project(new_project, user_id, project_uuid)
        await update_pipeline_db(
            request.app, project_uuid, new_project["workbench"], replace_pipeline
        )

    except ValidationError:
        raise web.HTTPBadRequest

    except ProjectInvalidRightsError:
        raise web.HTTPForbidden(
            reason=f"User {user_id} has no rights to write to project {project_uuid}"
        )
    except ProjectNotFoundError:
        raise web.HTTPNotFound

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
        with managed_resource(user_id, None, request.app) as rt:
            other_users = await rt.find_users_of_resource("project_id", project_uuid)
            if other_users:
                message = "Project is opened by another user. It cannot be deleted."
                if user_id in other_users:
                    message = "Project is still open. It cannot be deleted until it is closed."
                # we cannot delete that project
                raise web.HTTPForbidden(reason=message)

        await projects_api.delete_project(request, project_uuid, user_id)
    except ProjectInvalidRightsError:
        raise web.HTTPForbidden(
            reason=f"User {user_id} has no rights to delete project"
        )
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found")

    raise web.HTTPNoContent(content_type="application/json")


class HTTPConflict(web.HTTPClientError):
    # pylint: disable=too-many-ancestors
    status_code = 423


@login_required
@permission_required("project.open")
async def open_project(request: web.Request) -> web.Response:

    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    client_session_id = await request.json()
    try:
        with managed_resource(user_id, client_session_id, request.app) as rt:
            # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
            from .projects_api import get_project_for_user

            project = await get_project_for_user(
                request.app,
                project_uuid=project_uuid,
                user_id=user_id,
                include_templates=True,
            )

            # let's check if that project is already opened by someone
            other_users = await rt.find_users_of_resource("project_id", project_uuid)
            if other_users:
                raise HTTPConflict(reason="Project is already opened by another user")
            await rt.add("project_id", project_uuid)

        # user id opened project uuid
        await projects_api.start_project_interactive_services(request, project, user_id)

        return {"data": project}
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found")


@login_required
@permission_required("project.close")
async def close_project(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    client_session_id = await request.json()

    try:
        # ensure the project exists
        # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
        from .projects_api import get_project_for_user

        with managed_resource(user_id, client_session_id, request.app) as rt:
            await get_project_for_user(
                request.app,
                project_uuid=project_uuid,
                user_id=user_id,
                include_templates=True,
            )
            await rt.remove("project_id")
            other_users = await rt.find_users_of_resource("project_id", project_uuid)
            if not other_users:
                # only remove the services if no one else is using them now
                fire_and_forget_task(
                    projects_api.remove_project_interactive_services(
                        user_id, project_uuid, request.app
                    )
                )

        raise web.HTTPNoContent(content_type="application/json")
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found")


@login_required
@permission_required("project.read")
async def state_project(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    with managed_resource(user_id, None, request.app) as rt:
        # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
        from .projects_api import get_project_for_user

        project = await get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )

        return {
            "data": {
                "locked": len(
                    await rt.find_users_of_resource("project_id", project_uuid)
                )
                > 0
            }
        }


@login_required
@permission_required("project.read")
async def get_active_project(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    client_session_id = request.query["client_session_id"]

    try:
        project = None
        with managed_resource(user_id, client_session_id, request.app) as rt:
            # get user's projects
            list_project_ids = await rt.find("project_id")
            if list_project_ids:
                # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
                from .projects_api import get_project_for_user

                project = await get_project_for_user(
                    request.app,
                    project_uuid=list_project_ids[0],
                    user_id=user_id,
                    include_templates=True,
                )

        return {"data": project}
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason="Project not found")


@login_required
@permission_required("project.node.create")
async def create_node(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    body = await request.json()

    try:
        # ensure the project exists
        # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
        from .projects_api import get_project_for_user

        await get_project_for_user(
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
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found")


@login_required
@permission_required("project.node.read")
async def get_node(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    node_uuid = request.match_info.get("node_id")
    try:
        # ensure the project exists
        # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
        from .projects_api import get_project_for_user

        await get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )

        node_details = await projects_api.get_project_node(
            request, project_uuid, user_id, node_uuid
        )
        return {"data": node_details}
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found")


@login_required
@permission_required("project.node.delete")
async def delete_node(request: web.Request) -> web.Response:
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    node_uuid = request.match_info.get("node_id")
    try:
        # ensure the project exists
        # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
        from .projects_api import get_project_for_user

        await get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )

        await projects_api.delete_project_node(
            request, project_uuid, user_id, node_uuid
        )

        raise web.HTTPNoContent(content_type="application/json")
    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found")


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
