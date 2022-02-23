""" Handlers for CRUD operations on /projects/{*}/folder/{*}

"""

import logging

from aiohttp import web

from .._meta import api_version_prefix as VTAG
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_decorators import permission_required
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI

log = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.put(f"/{VTAG}/projects/{{project_uuid}}/folder/{{folder_id}}")
@login_required
@permission_required("project.folder.*")
async def set_folder(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    try:
        folder_id, project_uuid = (
            request.match_info["folder_id"],
            request.match_info["project_uuid"],
        )
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    return await db.set_folder(
        project_uuid=project_uuid, user_id=user_id, folder_id=int(folder_id)
    )


@routes.delete(f"/{VTAG}/projects/{{project_uuid}}/folder/{{folder_id}}")
@login_required
@permission_required("project.folder.*")
async def remove_folder(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    folder_id, project_uuid = (
        request.match_info["folder_id"],
        request.match_info["project_uuid"],
    )
    return await db.remove_folder(
        project_uuid=project_uuid, user_id=user_id, folder_id=int(folder_id)
    )
