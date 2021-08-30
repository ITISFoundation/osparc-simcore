import logging
from typing import List

from aiohttp import web
from models_library.users import GroupID, UserID
from servicelib.rest_utils import extract_and_validate
from simcore_service_webserver.clusters.models import Cluster
from simcore_service_webserver.groups_api import list_user_groups
from simcore_service_webserver.security_decorators import permission_required

from .._meta import api_version_prefix
from ..login.decorators import RQT_USERID_KEY, login_required
from .db import ClustersRepository

logger = logging.getLogger(__name__)

# API ROUTES HANDLERS ---------------------------------------------------------
routes = web.RouteTableDef()


@routes.get(f"/{api_version_prefix}/clusters", name="list_clusters_handler")
@login_required
@permission_required("clusters.read")
async def list_clusters_handler(request: web.Request) -> web.Response:
    await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]

    primary_group, std_groups, all_group = await list_user_groups(request.app, user_id)
    user_gids: List[GroupID] = [
        group["gid"] for group in ([primary_group] + std_groups + [all_group])
    ]

    clusters_repo = ClustersRepository(request)

    clusters_list: List[Cluster] = await clusters_repo.list_clusters_for_groups(
        user_gids
    )

    data = [d.dict(by_alias=True, exclude_unset=True) for d in clusters_list]

    return web.json_response(data={"data": data})


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
