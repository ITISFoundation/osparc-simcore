
import json
import logging

from aiohttp import web
from jsonschema import ValidationError

from servicelib.application_keys import APP_DB_ENGINE_KEY

from .. import security_permissions as sp
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_api import check_permission
from .projects_api import get_project_for_user, validate_project
from .projects_exceptions import (ProjectInvalidRightsError,
                                  ProjectNotFoundError)
from .projects_fakes import Fake
from .projects_models import ProjectDB

log = logging.getLogger(__name__)


@login_required
async def create_projects(request: web.Request):
    await check_permission(request, "project.create")

    # TODO: partial or complete project. Values taken as default if undefined??
    project = await request.json()

    user_id = request[RQT_USERID_KEY]
    # TODO: update metadata: uuid, ownership, timestamp, etc

    try:
        # validate data
        validate_project(request.app, project)

        # save data
        await ProjectDB.add_projects([project], user_id, db_engine=request.app[APP_DB_ENGINE_KEY])

    except ValidationError:
        raise web.HTTPBadRequest(reason="Invalid project data")

    except ProjectInvalidRightsError:
        raise web.HTTPUnauthorized

    else:
        raise web.HTTPCreated(text=json.dumps(project),
                                content_type='application/json')


@login_required
async def list_projects(request: web.Request):
    await check_permission(request, "project.read")

    # TODO: implement all query parameters as
    # in https://www.ibm.com/support/knowledgecenter/en/SSCRJU_3.2.0/com.ibm.swg.im.infosphere.streams.rest.api.doc/doc/restapis-queryparms-list.html

    uid = request[RQT_USERID_KEY]
    ptype = request.query.get('type', 'user')

    projects_list = []
    if ptype in ("template", "all"):
        projects_list += [prj.data for prj in Fake.projects.values() if prj.template]
        projects_list += await ProjectDB.load_template_projects(db_engine=request.app[APP_DB_ENGINE_KEY])

    if ptype in ("user", "all"):
        projects_list += await ProjectDB.load_user_projects(user_id=uid, db_engine=request.app[APP_DB_ENGINE_KEY])


    start = int(request.query.get('start', 0))
    count = int(request.query.get('count',len(projects_list)))

    stop = min(start+count, len(projects_list))
    projects_list = projects_list[start:stop]

    # validate response
    validated_projects = []
    for project in projects_list:
        try:
            validate_project(request.app, project)
            validated_projects.append(project)
        except ValidationError:
            log.exception("Skipping invalid project from list")
            continue

    return {'data': validated_projects}


@login_required
async def get_project(request: web.Request):
    project = await get_project_for_user(request,
        project_uuid=request.match_info.get("project_id"),
        user_id=request[RQT_USERID_KEY]
    )

    return {
        'data': project
    }


@login_required
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
    new_values = await request.json()

    dbe = request.config_dict[APP_DB_ENGINE_KEY]

    await check_permission(request, sp.or_("project.update", "project.workbench.node.inputs.update"),
    context={
        'db_engine': dbe,
        'project_id': project_uuid,
        'user_id': user_id,
        'new_data': new_values
    })

    try:
        validate_project(request.app, new_values)
        await ProjectDB.update_user_project(new_values, user_id, project_uuid, db_engine=dbe)

    except ValidationError:
        raise web.HTTPBadRequest

    except ProjectNotFoundError:
        raise web.HTTPNotFound

    return {'data': new_values}


@login_required
async def patch_project(_request: web.Request):
    """
        Client sends a patch and return updated project
        PATCH
    """
    # TODO: implement patch with diff as body!
    raise NotImplementedError()


@login_required
async def delete_project(request: web.Request):
    # TODO: replace by decorator since it checks again authentication
    await check_permission(request, "project.delete")

    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")

    try:
        await ProjectDB.delete_user_project(user_id, project_uuid, db_engine=request.app[APP_DB_ENGINE_KEY])
    except ProjectNotFoundError:
        raise web.HTTPNotFound

    raise web.HTTPNoContent(content_type='application/json')
