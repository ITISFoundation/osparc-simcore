""" Handlers for standard operations on /projects colletions

SEE https://google.aip.dev/131
SEE https://google.aip.dev/132
SEE https://google.aip.dev/133
SEE https://google.aip.dev/134
SEE https://google.aip.dev/135

"""

import asyncio
import json
import logging
from typing import Any, Coroutine, Dict, List, Optional, Set

from aiohttp import web
from jsonschema import ValidationError
from models_library.projects import ProjectID
from models_library.projects_state import ProjectStatus
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
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
from . import _core_get, _core_notify, _core_states
from ._core_delete import create_delete_project_task
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
            source_project = await _core_get.get_project_for_user(
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
        await _core_get.validate_project(request.app, new_project)

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
                async with _core_notify.lock_project_and_notify_state_update(
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
        new_project = await _core_states.add_project_states_for_user(
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
    except (asyncio.CancelledError, asyncio.TimeoutError):
        log.warning(
            "cancelled creation of project for user '%s', cleaning up", f"{user_id=}"
        )
        # TODO: this is a temp solution that hides this project from the listing until
        #       the delete_project_task completes
        # TODO: see https://github.com/ITISFoundation/osparc-simcore/pull/2522
        await db.set_hidden_flag(new_project["uuid"], enabled=True)
        # fire+forget: this operation can be heavy, specially with data deletion
        create_delete_project_task(request.app, new_project["uuid"], user_id)
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
                _core_states.add_project_states_for_user(
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
    page = Page[ProjectDict].parse_obj(
        paginate_data(
            chunk=projects,
            request_url=request.url,
            total=total_number_projects,
            limit=limit,
            offset=offset,
        )
    )
    return page.dict(**RESPONSE_MODEL_POLICY)


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
        project = await _core_get.get_project_for_user(
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
            # TODO: lack of permissions should be notified with https://httpstatuses.com/403 web.HTTPForbidden
            raise web.HTTPNotFound(
                reason=(
                    f"Project '{project_uuid}' uses unavailable services. Please ask "
                    f"for permission for the following services {formatted_services}"
                )
            )

        if new_uuid := request.get(RQ_REQUESTED_REPO_PROJECT_UUID_KEY):
            project["uuid"] = new_uuid

        return {"data": project}

    except ProjectInvalidRightsError as exc:
        raise web.HTTPForbidden(
            reason=f"You do not have sufficient rights to read project {project_uuid}"
        ) from exc
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from exc


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

        # Prune state field (just in case)
        new_project.pop("state", None)

    except AttributeError as err:
        # NOTE: if new_project is not a dict, .pop will raise this error
        raise web.HTTPBadRequest(
            reason="Invalid request payload, expected a project model"
        ) from err
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(reason="Invalid request body") from exc

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
        await _core_get.validate_project(request.app, new_project)

        current_project = await _core_get.get_project_for_user(
            request.app,
            project_uuid=f"{project_uuid}",
            user_id=user_id,
            include_templates=True,
            include_state=True,
        )

        if current_project["accessRights"] != new_project["accessRights"]:
            await check_permission(request, "project.access_rights.update")

        if await director_v2_api.is_pipeline_running(
            request.app, user_id, project_uuid
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
                    reason=f"Project {project_uuid} cannot be modified while pipeline is still running."
                )

        new_project = await db.replace_user_project(
            new_project, user_id, f"{project_uuid}", include_templates=True
        )
        await director_v2_api.create_or_update_pipeline(
            request.app, user_id, project_uuid
        )
        # Appends state
        new_project = await _core_states.add_project_states_for_user(
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
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    try:
        project_uuid = request.match_info["project_id"]
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    try:

        # exists?
        await _core_get.get_project_for_user(
            request.app,
            project_uuid=project_uuid,
            user_id=user_id,
            include_templates=True,
        )

        # has access?
        # TODO: optimize since this also check existence and read access
        await db.raise_if_cannot_delete(user_id, project_uuid)

        # in use?
        project_users: Set[int] = set()
        with managed_resource(user_id, None, request.app) as rt:
            project_users = {
                user_session.user_id
                for user_session in await rt.find_users_of_resource(
                    PROJECT_ID_KEY, project_uuid
                )
            }
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

        # DELETE ---
        # TODO: this is a temp solution that hides this project from the listing until
        #       the delete_project_task completes
        # TODO: see https://github.com/ITISFoundation/osparc-simcore/pull/2522
        await db.set_hidden_flag(f"{project_uuid}", enabled=True)

        # fire+forget: this operation can be heavy, specially with data deletion
        task = create_delete_project_task(request.app, project_uuid, user_id)
        log.debug("Spawned task %s to delete %s", task.get_name(), f"{project_uuid=}")

    except ProjectInvalidRightsError as err:
        raise web.HTTPForbidden(
            reason="You do not have sufficient rights to delete this project"
        ) from err
    except ProjectNotFoundError as err:
        raise web.HTTPNotFound(reason=f"Project {project_uuid} not found") from err

    raise web.HTTPNoContent(content_type="application/json")
