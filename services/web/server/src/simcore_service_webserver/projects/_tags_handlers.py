""" Handlers for CRUD operations on /projects/{*}/tags/{*}

"""

import logging

from aiohttp import web
from servicelib.request_keys import RQT_USERID_KEY

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from .db import APP_PROJECT_DBAPI, ProjectDBAPI

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.put(f"/{API_VTAG}/projects/{{project_uuid}}/tags/{{tag_id}}", name="add_tag")
@login_required
@permission_required("project.tag.*")
async def add_tag(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    try:
        tag_id, project_uuid = (
            request.match_info["tag_id"],
            request.match_info["project_uuid"],
        )
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    return await db.add_tag(
        project_uuid=project_uuid, user_id=user_id, tag_id=int(tag_id)
    )


@routes.delete(
    f"/{API_VTAG}/projects/{{project_uuid}}/tags/{{tag_id}}", name="remove_tag"
)
@login_required
@permission_required("project.tag.*")
async def remove_tag(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]

    tag_id, project_uuid = (
        request.match_info["tag_id"],
        request.match_info["project_uuid"],
    )
    return await db.remove_tag(
        project_uuid=project_uuid, user_id=user_id, tag_id=int(tag_id)
    )
