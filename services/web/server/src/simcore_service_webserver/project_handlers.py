# pylint: disable=global-statement


import json
import logging
from collections import defaultdict, namedtuple

from aiohttp import web

from .login.decorators import RQT_USERID_KEY, login_required
from .resources import resources

log = logging.getLogger(__name__)


# TODO: move tables to db

# FAKES--------------------------------------------------
ProjectItem = namedtuple("ProjectItem", "id template data".split())
_fake_projects = {}

_fake_user_to_projects_map = defaultdict(list)

def init_db():
    global _fake_user_to_projects_map
    global _fake_projects

    # user projects
    with resources.stream("data/fake-user-projects.json") as f:
        projects = json.load(f)

    for i, prj in enumerate(projects):
        pid, uid = prj['projectUuid'], i
        _fake_projects[pid] = ProjectItem(id=pid, template=False, data=prj)
        _fake_user_to_projects_map[uid].append(pid)

    # templates
    with resources.stream("data/fake-template-projects.json") as f:
        projects += json.load(f)

    for prj in projects:
        pid = prj['projectUuid']
        _fake_projects[pid] =  ProjectItem(id=pid, template=True, data=prj)

init_db()
#--------------------------------------------------


@login_required
async def list_projects(request: web.Request):
    uid = request[RQT_USERID_KEY]
    only_templates = request.match_info.get("template", False)

    if only_templates:
        projects = [prj for prj in _fake_user_to_projects_map if prj.template]
    else:
        projects = [_fake_projects[pid]
                        for pid in _fake_user_to_projects_map.get(uid, list())]

    return {'data': projects}


@login_required
async def create_projects(request: web.Request):
    global _fake_user_to_projects_map
    global _fake_projects

    project = await request.json()
    pid, uid = project['projectUuid'], request[RQT_USERID_KEY]

    _fake_projects[pid] = ProjectItem(id=pid, template=False, data=project)
    _fake_user_to_projects_map[uid].append(pid)

    raise web.HTTPCreated(text=json.dumps(project),
                          content_type='application/json')


@login_required
async def get_project(request: web.Request):
    pid, uid = request.match_info.get("project_id"), request[RQT_USERID_KEY]

    project = _fake_projects.get(pid)
    if not project:
        raise web.HTTPNotFound(content_type='application/json')

    if pid in _fake_user_to_projects_map.get(uid):
        msg = "User %s does not own requested project %s" %(uid, pid)
        raise web.HTTPForbidden(reason=msg, content_type='application/json')

    return {'data': project}


@login_required
async def update_project(request: web.Request):
    global _fake_projects

    project = await request.json()
    pid, uid = project['projectUuid'], request[RQT_USERID_KEY]

    current_project = _fake_projects.get(pid)
    if not current_project:
        raise web.HTTPNotFound(content_type='application/json')

    if pid in _fake_user_to_projects_map.get(uid):
        msg = "User %s does not own requested project %s" %(uid, pid)
        raise web.HTTPForbidden(reason=msg, content_type='application/json')

    for key in project:
        current_project[key] = project[key] # FIXME: update only rhs branches


@login_required
async def delete_project(request: web.Request):
    global _fake_projects
    global _fake_user_to_projects_map

    pid, uid = request.match_info.get("project_id"), request[RQT_USERID_KEY]

    if pid in _fake_user_to_projects_map.get(uid):
        msg = "User %s does not own requested project %s" %(uid, pid)
        raise web.HTTPForbidden(reason=msg, content_type='application/json')

    # TODO: sharing policy: can user delete if shared?
    _fake_projects.pop(pid, None)
    for _, project_ids in _fake_user_to_projects_map.items():
        project_ids[:] = [i for i in project_ids if i!=pid]
