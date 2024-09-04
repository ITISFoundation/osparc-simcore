""" Handlers for CRUD operations on /projects/{*}/tags/{*}

"""

import logging

from aiohttp import web
from models_library.projects import ProjectID
from servicelib.request_keys import RQT_USERID_KEY
from simcore_service_webserver.utils_aiohttp import envelope_json_response

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from . import _tags_api as tags_api

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.put(f"/{API_VTAG}/projects/{{project_uuid}}/tags/{{tag_id}}", name="add_tag")
@login_required
@permission_required("project.tag.*")
async def add_tag(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]

    try:
        tag_id, project_uuid = (
            request.match_info["tag_id"],
            request.match_info["project_uuid"],
        )
    except KeyError as err:
        raise web.HTTPBadRequest(reason=f"Invalid request parameter {err}") from err

    project = await tags_api.add_tag(
        request.app,
        user_id=user_id,
        project_uuid=ProjectID(project_uuid),
        tag_id=int(tag_id),
    )
    return envelope_json_response(project)


@routes.delete(
    f"/{API_VTAG}/projects/{{project_uuid}}/tags/{{tag_id}}", name="remove_tag"
)
@login_required
@permission_required("project.tag.*")
async def remove_tag(request: web.Request):
    user_id: int = request[RQT_USERID_KEY]

    tag_id, project_uuid = (
        request.match_info["tag_id"],
        request.match_info["project_uuid"],
    )
    project = await tags_api.remove_tag(
        request.app,
        user_id=user_id,
        project_uuid=ProjectID(project_uuid),
        tag_id=int(tag_id),
    )

    return envelope_json_response(project)
