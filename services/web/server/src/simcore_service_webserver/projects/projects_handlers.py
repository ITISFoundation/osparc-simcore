# pylint: disable=global-statement


import json
import logging
from typing import Dict, List

from aiohttp import web
from jsonschema import ValidationError

from servicelib.application_keys import (APP_DB_ENGINE_KEY,
                                         APP_JSONSCHEMA_SPECS_KEY)
from servicelib.jsonschema_validation import \
    validate_instance as validate_project

from ..login.decorators import RQT_USERID_KEY, login_required
from .config import CONFIG_SECTION_NAME
from .projects_exceptions import (ProjectInvalidRightsError,
                                  ProjectNotFoundError)
from .projects_fakes import Fake
from .projects_models import ProjectDB

log = logging.getLogger(__name__)


ANONYMOUS_UID = -1 # For testing purposes

@login_required
async def create_projects(request: web.Request):
    project = await request.json()
    try:
        _validate(request.app, [project])
    except ValidationError:
        raise web.HTTPBadRequest

    _, uid = project['uuid'], request.get(RQT_USERID_KEY, ANONYMOUS_UID)
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
        projects_list += await ProjectDB.load_template_projects(db_engine=request.app[APP_DB_ENGINE_KEY])

    if ptype in ("user", "all"):
        projects_list += await ProjectDB.load_user_projects(user_id=uid, db_engine=request.app[APP_DB_ENGINE_KEY])

    start = int(request.query.get('start', 0))
    count = int(request.query.get('count',len(projects_list)))

    stop = min(start+count, len(projects_list))
    projects_list = projects_list[start:stop]
    # validate response
    _validate(request.app, projects_list)

    return {'data': projects_list}


@login_required
async def get_project(request: web.Request):
    project_uuid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    if project_uuid in Fake.projects:
        return {'data': Fake.projects[project_uuid].data}

    try:
        project = await ProjectDB.get_user_project(uid, project_uuid, db_engine=request.app[APP_DB_ENGINE_KEY])
        _validate(request.app, [project])
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
        _validate(request.app, [new_values])
    except ValidationError:
        raise web.HTTPBadRequest

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


def _validate(app: web.Application, projects: List[Dict]):
    project_schema = app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME]
    for project in projects:
        validate_project(project, project_schema)
