import logging

from aiohttp import web
from models_library.users import UserID
from servicelib.application_keys import APP_DB_ENGINE_KEY
from servicelib.rest_utils import extract_and_validate
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_service_webserver.groups_api import list_user_groups
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
    await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    db_engine = request.app[APP_DB_ENGINE_KEY]

    primary_group, std_groups, all_group = await list_user_groups(request.app, user_id)

    data = []
    # async with db_engine.acquire() as conn:
    #     async for row in conn.execute()

    return web.json_response(data=data)


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
