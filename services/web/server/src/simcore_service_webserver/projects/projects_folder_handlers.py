""" Handlers for CRUD operations on /projects-with-folder/{*}

"""

import logging

from aiohttp import web

from .._meta import api_version_prefix as VTAG
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_decorators import permission_required
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_handlers import get_project, list_projects

log = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/projects-with-folder")
@login_required
@permission_required("project.read")
async def list_projects_with_folder(request: web.Request):
    projects = await list_projects(request)
    print("projects", projects)
    return projects


@routes.get(f"/{VTAG}/projects-with-folder/{{project_id}}")
@login_required
@permission_required("project.read")
async def get_project_with_folder(request: web.Request):
    project = await get_project(request)
    print("project", project)
    return project


@routes.put(f"/{VTAG}/projects-with-folder/{{project_id}}/folder/{{folder_id}}")
@login_required
@permission_required("project.folder.*")
async def set_folder_to_project(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    try:
        folder_id, project_id = (
            request.match_info["folder_id"],
            request.match_info["project_id"],
        )
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    return await db.set_folder(
        project_id=project_id, user_id=user_id, folder_id=int(folder_id)
    )


@routes.delete(f"/{VTAG}/projects-with-folder/{{project_id}}/folder/{{folder_id}}")
@login_required
@permission_required("project.folder.*")
async def remove_folder_from_project(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    folder_id, project_id = (
        request.match_info["folder_id"],
        request.match_info["project_id"],
    )
    return await db.remove_folder(
        project_id=project_id, user_id=user_id, folder_id=int(folder_id)
    )
