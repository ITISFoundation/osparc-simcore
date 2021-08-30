import logging
from typing import List

from aiohttp import web
from models_library.users import GroupID, UserID
from servicelib.rest_utils import extract_and_validate
from simcore_postgres_database.models.clusters import ClusterType
from simcore_service_webserver.clusters.exceptions import ClusterNotFoundError
from simcore_service_webserver.clusters.models import Cluster, ClusterCreate
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

    clusters_repo = ClustersRepository(request)

    clusters_list: List[Cluster] = await clusters_repo.list_clusters_for_user_groups(
        GroupID(primary_group["gid"]),
        [GroupID(g["gid"]) for g in std_groups],
        GroupID(all_group["gid"]),
    )

    data = [d.dict(by_alias=True) for d in clusters_list]

    return web.json_response(data={"data": data})


@routes.post(f"/{api_version_prefix}/clusters", name="create_cluster_handler")
@login_required
@permission_required("clusters.create")
async def create_cluster_handler(request: web.Request) -> web.Response:
    _, _, body = await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    primary_group, _, _ = await list_user_groups(request.app, user_id)

    new_cluster = ClusterCreate(
        name=body.name,
        description=body.description if hasattr(body, "description") else None,
        type=ClusterType.ON_PREMISE,
        owner=primary_group["gid"],
    )

    clusters_repo = ClustersRepository(request)
    new_cluster = await clusters_repo.create_cluster(new_cluster)

    data = new_cluster.dict(by_alias=True)
    return web.json_response(data={"data": data})


@routes.get(f"/{api_version_prefix}/clusters/{{id}}", name="get_cluster_handler")
@login_required
@permission_required("clusters.read")
async def get_cluster_handler(request: web.Request) -> web.Response:
    path, _, _ = await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    primary_group, std_groups, all_group = await list_user_groups(request.app, user_id)

    clusters_repo = ClustersRepository(request)
    try:
        cluster = clusters_repo.get_cluster(
            GroupID(primary_group["gid"]),
            [GroupID(g["gid"]) for g in std_groups],
            GroupID(all_group["gid"]),
            path["id"],
        )
    except ClusterNotFoundError as exc:
        raise web.HTTPNotFound(reason=exc.msg)


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
