from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from .._meta import API_VTAG as VTAG
from ..login.decorators import get_user_id, login_required
from ..products.api import get_product_name
from ..projects._common_models import ProjectPathParams
from ..security.decorators import permission_required
from . import _trash_api

routes = web.RouteTableDef()


@routes.delete(f"/{VTAG}/trash", name="empty_trash")
@login_required
@permission_required("project.delete")
async def empty_trash(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)

    await _trash_api.empty_trash(
        request.app, product_name=product_name, user_id=user_id
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# Projects
#


@routes.post(f"/{VTAG}/projects/{{project_id}}:trash", name="trash_project")
@login_required
@permission_required("project.delete")
async def trash_project(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    await _trash_api.update_project(
        request.app,
        product_name=product_name,
        user_id=user_id,
        project_id=path_params.project_id,
        trashed=True,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{VTAG}/projects/{{project_uuid}}:untrash", name="untrash_project")
@login_required
@permission_required("project.delete")
async def untrash_project(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    await _trash_api.update_project(
        request.app,
        product_name=product_name,
        user_id=user_id,
        project_id=path_params.project_id,
        trashed=False,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
