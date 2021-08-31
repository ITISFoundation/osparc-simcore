import logging
from typing import List

from aiohttp import web
from models_library.users import GroupID, UserID
from servicelib.rest_utils import extract_and_validate

from .._meta import api_version_prefix
from ..groups_api import list_user_groups
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_decorators import permission_required
from .db import ClustersRepository
from .exceptions import ClusterAccessForbidden, ClusterNotFoundError
from .models import Cluster, ClusterCreate, ClusterPatch

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

    clusters_list: List[Cluster] = await clusters_repo.list_clusters(
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
        name=body.name if hasattr(body, "name") else None,
        description=body.description if hasattr(body, "description") else None,
        type=body.type if hasattr(body, "type") else None,
        owner=primary_group["gid"],
    )

    clusters_repo = ClustersRepository(request)
    new_cluster = await clusters_repo.create_cluster(new_cluster)

    data = new_cluster.dict(by_alias=True)
    return web.json_response(data={"data": data}, status=web.HTTPCreated.status_code)


@routes.get(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="get_cluster_handler"
)
@login_required
@permission_required("clusters.read")
async def get_cluster_handler(request: web.Request) -> web.Response:
    path, _, _ = await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    primary_group, std_groups, all_group = await list_user_groups(request.app, user_id)

    clusters_repo = ClustersRepository(request)
    try:
        cluster = await clusters_repo.get_cluster(
            GroupID(primary_group["gid"]),
            [GroupID(g["gid"]) for g in std_groups],
            GroupID(all_group["gid"]),
            path["cluster_id"],
        )
        data = cluster.dict(by_alias=True)
        return web.json_response(data={"data": data})
    except ClusterNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"{exc}")
    except ClusterAccessForbidden as exc:
        raise web.HTTPForbidden(reason=f"{exc}")


@routes.patch(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="update_cluster_handler"
)
@login_required
@permission_required("clusters.write")
async def update_cluster_handler(request: web.Request) -> web.Response:
    path, _, body = await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    primary_group, std_groups, all_group = await list_user_groups(request.app, user_id)

    updated_cluster = ClusterPatch(
        name=body.name if hasattr(body, "name") else None,
        description=body.description if hasattr(body, "description") else None,
        type=body.type if hasattr(body, "type") else None,
        owner=body.owner if hasattr(body, "owner") else None,
        access_rights=body.access_rights if hasattr(body, "access_rights") else None,
    )

    clusters_repo = ClustersRepository(request)
    try:
        cluster = await clusters_repo.update_cluster(
            GroupID(primary_group["gid"]),
            [GroupID(g["gid"]) for g in std_groups],
            GroupID(all_group["gid"]),
            path["cluster_id"],
            updated_cluster,
        )
        data = cluster.dict(by_alias=True)
        return web.json_response(data={"data": data})
    except ClusterNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"{exc}")
    except ClusterAccessForbidden as exc:
        raise web.HTTPForbidden(reason=f"{exc}")


@routes.delete(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="delete_cluster_handler"
)
@login_required
@permission_required("clusters.delete")
async def delete_cluster_handler(request: web.Request) -> web.Response:
    raise web.HTTPNotImplemented(reason="not yet implemented")
