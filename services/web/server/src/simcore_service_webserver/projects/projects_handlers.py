# pylint: disable=global-statement


import json
import logging

from aiohttp import web

from ..login.decorators import RQT_USERID_KEY, login_required
from .projects_fakes import Fake

log = logging.getLogger(__name__)


ANONYMOUS_UID = -1 # For testing purposes


@login_required
async def list_projects(request: web.Request):
    uid = request.get(RQT_USERID_KEY, ANONYMOUS_UID)
    # TODO: implement all query parameters as in https://www.ibm.com/support/knowledgecenter/en/SSCRJU_3.2.0/com.ibm.swg.im.infosphere.streams.rest.api.doc/doc/restapis-queryparms-list.html
    ptype = request.query.get('type', 'user')

    projects = []
    if ptype in ("template", "all"):
        projects += [prj.data for prj in Fake.projects.values() if prj.template]

    if ptype in ("user", "all"):
        projects += [Fake.projects[pid].data
                        for pid in Fake.user_to_projects_map.get(uid, list())]

    start = int(request.query.get('start', 0))
    count = int(request.query.get('count',len(projects)))

    stop = min(start+count, len(projects))
    projects = projects[start:stop]
    return {'data': projects}


@login_required
async def create_projects(request: web.Request):
    project = await request.json()
    # TODO: validate here
    #TODO: create as template .. ?type=template

    pid, uid = project['projectUuid'], request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    Fake.projects[pid] = Fake.ProjectItem(id=pid, template=False, data=project)
    Fake.user_to_projects_map[uid].append(pid)

    raise web.HTTPCreated(text=json.dumps(project),
                          content_type='application/json')


@login_required
async def get_project(request: web.Request):
    pid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    project = Fake.projects.get(pid)
    if not project:
        raise web.HTTPNotFound(content_type='application/json')

    assert_ownership(pid, uid)

    return {'data': project.data}


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
    pid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    new_values = await request.json()
    # TODO: validate project data

    current_project = Fake.projects.get(pid)
    if not current_project:
        raise web.HTTPNotFound(content_type='application/json')

    assert_ownership(pid, uid)

    new_project = current_project._asdict()
    new_project['data'] = new_values
    Fake.projects[pid] = Fake.ProjectItem(**new_project)

@login_required
async def delete_project(request: web.Request):
    pid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    assert_ownership(pid, uid)

    # TODO: sharing policy: can user delete if shared?
    Fake.projects.pop(pid, None)
    delete = []
    for key, project_ids in Fake.user_to_projects_map.items():
        project_ids[:] = [i for i in project_ids if i!=pid]
        if not project_ids:
            delete.append(key)

    for key in delete:
        Fake.user_to_projects_map.pop(key, None)

    raise web.HTTPNoContent(content_type='application/json')



# HELPERS -------------

def assert_ownership(pid, uid):
    project = Fake.projects.get(pid, None)
    if project and not project.template:
        if pid not in Fake.user_to_projects_map.get(uid):
            msg = "User %s does not own requested project %s" %(uid, pid)
            raise web.HTTPForbidden(reason=msg, content_type='application/json')
