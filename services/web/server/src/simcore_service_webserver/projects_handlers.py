# pylint: disable=global-statement


import json
import logging

from aiohttp import web

from .login.decorators import RQT_USERID_KEY, login_required
from .projects_fakes import Fake

log = logging.getLogger(__name__)


ANONYMOUS_UID = -1 # For testing purposes


#@login_required
async def list_projects(request: web.Request):
    uid = request.get(RQT_USERID_KEY, ANONYMOUS_UID)
    only_templates = request.match_info.get("template", False)

    if only_templates:
        projects = [prj for prj in Fake.user_to_projects_map if prj.template]
    else:
        projects = [Fake.projects[pid]
                        for pid in Fake.user_to_projects_map.get(uid, list())]

    return {'data': projects}


#@login_required
async def create_projects(request: web.Request):
    project = await request.json()
    # TODO: validate here

    pid, uid = project['projectUuid'], request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    Fake.projects[pid] = Fake.ProjectItem(id=pid, template=False, data=project)
    Fake.user_to_projects_map[uid].append(pid)

    raise web.HTTPCreated(text=json.dumps(project),
                          content_type='application/json')


#@login_required
async def get_project(request: web.Request):
    pid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    project = Fake.projects.get(pid)
    if not project:
        raise web.HTTPNotFound(content_type='application/json')

    if pid in Fake.user_to_projects_map.get(uid):
        msg = "User %s does not own requested project %s" %(uid, pid)
        raise web.HTTPForbidden(reason=msg, content_type='application/json')

    return {'data': project}


#@login_required
async def update_project(request: web.Request):
    project = await request.json()
    # TODO: validate project data

    import pdb; pdb.set_trace()

    pid, uid = project['projectUuid'], request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    current_project = Fake.projects.get(pid)
    if not current_project:
        raise web.HTTPNotFound(content_type='application/json')

    if pid in Fake.user_to_projects_map.get(uid):
        msg = "User %s does not own requested project %s" %(uid, pid)
        raise web.HTTPForbidden(reason=msg, content_type='application/json')

    for key in project:
        current_project[key] = project[key] # FIXME: update only rhs branches


#@login_required
async def delete_project(request: web.Request):
    pid, uid = request.match_info.get("project_id"), request.get(RQT_USERID_KEY, ANONYMOUS_UID)

    if pid in Fake.user_to_projects_map.get(uid):
        msg = "User %s does not own requested project %s" %(uid, pid)
        raise web.HTTPForbidden(reason=msg, content_type='application/json')

    # TODO: sharing policy: can user delete if shared?
    Fake.projects.pop(pid, None)
    for _, project_ids in Fake.user_to_projects_map.items():
        project_ids[:] = [i for i in project_ids if i!=pid]
