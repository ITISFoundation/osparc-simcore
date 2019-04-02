# pylint: disable=global-statement


import json
import logging

from aiohttp import web

from servicelib.application_keys import APP_DB_ENGINE_KEY

from ..login.decorators import RQT_USERID_KEY, login_required
from .projects_fakes import Fake
from .projects_models import ProjectDB
from .projects_exceptions import ProjectNotFoundError, ProjectInvalidRightsError
log = logging.getLogger(__name__)


ANONYMOUS_UID = -1 # For testing purposes

@login_required
async def create_projects(request: web.Request):
    project = await request.json()
    pid, uid = project['uuid'], request.get(RQT_USERID_KEY, ANONYMOUS_UID)
    try:
        await ProjectDB.add_projects([project], uid, db_engine=request.app[APP_DB_ENGINE_KEY])
    except ProjectInvalidRightsError:
        raise web.HTTPUnauthorized

    raise web.HTTPCreated(text=json.dumps(project),
                          content_type='application/json')

@login_required
async def list_projects(request: web.Request):
    uid = request.get(RQT_USERID_KEY, ANONYMOUS_UID)
    # TODO: implement all query parameters as in https://www.ibm.com/support/knowledgecenter/en/SSCRJU_3.2.0/com.ibm.swg.im.infosphere.streams.rest.api.doc/doc/restapis-queryparms-list.html
    ptype = request.query.get('type', 'user')
    projects_list = []
    if ptype in ("template", "all"):
        projects_list += [prj.data for prj in Fake.projects.values() if prj.template]

    if ptype in ("user", "all"):
        projects_list += await ProjectDB.load_user_projects(user_id=uid, db_engine=request.app[APP_DB_ENGINE_KEY])

    start = int(request.query.get('start', 0))
    count = int(request.query.get('count',len(projects_list)))

    stop = min(start+count, len(projects_list))
    projects_list = projects_list[start:stop]
    return {'data': projects_list}


@login_required
async def get_project(request: web.Request):
    project_uuid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    try:
        project = await ProjectDB.get_user_project(uid, project_uuid, db_engine=request.app[APP_DB_ENGINE_KEY])
        return {'data': project}
    except ProjectNotFoundError:
        raise web.HTTPNotFound

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
    project_uuid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    new_values = await request.json()
    try:
        await ProjectDB.update_user_project(new_values, uid, project_uuid, db_engine=request.app[APP_DB_ENGINE_KEY])
    except ProjectNotFoundError:
        raise web.HTTPNotFound

@login_required
async def delete_project(request: web.Request):
    project_uuid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    try:
        await ProjectDB.delete_user_project(uid, project_uuid, db_engine=request.app[APP_DB_ENGINE_KEY])
    except ProjectNotFoundError:
        raise web.HTTPNotFound

    raise web.HTTPNoContent(content_type='application/json')
