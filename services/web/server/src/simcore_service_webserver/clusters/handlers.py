import logging

from aiohttp import web
from servicelib.application_keys import APP_DB_ENGINE_KEY
from servicelib.rest_utils import extract_and_validate
from simcore_service_webserver.security_decorators import permission_required

from .._meta import api_version_prefix
from ..login.decorators import RQT_USERID_KEY, login_required

logger = logging.getLogger(__name__)

# API ROUTES HANDLERS ---------------------------------------------------------
routes = web.RouteTableDef()


@routes.get(f"/{api_version_prefix}/clusters", name="list_clusters_handler")
@login_required
@permission_required("clusters.read")
async def list_clusters_handler(request: web.Request) -> web.Response:
    params, query, body = await extract_and_validate(request)
    user_id: int = request[RQT_USERID_KEY]
    db_engine = request.app[APP_DB_ENGINE_KEY]

    async with db_engine.acquire() as conn:
        pass
    raise web.HTTPNotImplemented(reason="not yet implemented")


@routes.post(f"/{api_version_prefix}/clusters", name="create_cluster_handler")
@login_required
@permission_required("clusters.create")
async def create_cluster_handler(request: web.Request) -> web.Response:
    raise web.HTTPNotImplemented(reason="not yet implemented")


@routes.get(f"/{api_version_prefix}/clusters/{{id}}", name="get_cluster_handler")
@login_required
@permission_required("clusters.read")
async def get_cluster_handler(request: web.Request) -> web.Response:
    raise web.HTTPNotImplemented(reason="not yet implemented")


@routes.patch(f"/{api_version_prefix}/clusters/{{id}}", name="update_cluster_handler")
@login_required
@permission_required("clusters.write")
async def update_cluster_handler(request: web.Request) -> web.Response:
    raise web.HTTPNotImplemented(reason="not yet implemented")


@routes.delete(f"/{api_version_prefix}/clusters/{{id}}", name="delete_cluster_handler")
@login_required
@permission_required("clusters.delete")
async def delete_cluster_handler(request: web.Request) -> web.Response:
    raise web.HTTPNotImplemented(reason="not yet implemented")
