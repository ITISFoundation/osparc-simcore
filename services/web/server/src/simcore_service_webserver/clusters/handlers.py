import logging

from aiohttp import web
from models_library.users import UserID
from pydantic import ValidationError
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.json_serialization import json_dumps

from .. import director_v2_api
from .._meta import api_version_prefix
from ..director_v2_exceptions import ClusterAccessForbidden, ClusterNotFoundError
from ..director_v2_models import ClusterCreate, ClusterPatch
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_decorators import permission_required

logger = logging.getLogger(__name__)

# API ROUTES HANDLERS ---------------------------------------------------------
routes = web.RouteTableDef()


@routes.post(f"/{api_version_prefix}/clusters", name="create_cluster_handler")
@login_required
@permission_required("clusters.create")
async def create_cluster_handler(request: web.Request) -> web.Response:
    await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    body = await request.json()
    assert body  # no sec
    try:
        new_cluster = ClusterCreate(
            name=body.get("name"),
            description=body.get("description"),
            type=body.get("type"),
            endpoint=body.get("endpoint"),
            authentication=body.get("authentication"),
            owner=None,
            thumbnail=body.get("thumbnail", None),
        )
        created_cluster = await director_v2_api.create_cluster(
            request.app, user_id=user_id, new_cluster=new_cluster
        )
        return web.json_response(
            data={"data": created_cluster},
            status=web.HTTPCreated.status_code,
            dumps=json_dumps,
        )
    except ValidationError as exc:
        raise web.HTTPUnprocessableEntity(
            reason=f"Invalid cluster definition: {exc} "
        ) from exc


@routes.get(f"/{api_version_prefix}/clusters", name="list_clusters_handler")
@login_required
@permission_required("clusters.read")
async def list_clusters_handler(request: web.Request) -> web.Response:
    await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    data = await director_v2_api.list_clusters(request.app, user_id)
    return web.json_response(data={"data": data}, dumps=json_dumps)


@routes.get(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="get_cluster_handler"
)
@login_required
@permission_required("clusters.read")
async def get_cluster_handler(request: web.Request) -> web.Response:
    path, _, _ = await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    try:
        cluster = await director_v2_api.get_cluster(
            request.app, user_id, cluster_id=path["cluster_id"]
        )
        return web.json_response(data={"data": cluster}, dumps=json_dumps)
    except ClusterNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"{exc}") from exc
    except ClusterAccessForbidden as exc:
        raise web.HTTPForbidden(reason=f"{exc}") from exc


@routes.patch(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="update_cluster_handler"
)
@login_required
@permission_required("clusters.write")
async def update_cluster_handler(request: web.Request) -> web.Response:
    path, _, _ = await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    body = await request.json()
    try:
        cluster_update = ClusterPatch.parse_obj(body)
        updated_cluster = await director_v2_api.update_cluster(
            request.app, user_id, path["cluster_id"], cluster_update
        )
        return web.json_response(data={"data": updated_cluster}, dumps=json_dumps)
    except ValidationError as exc:
        raise web.HTTPUnprocessableEntity(
            reason=f"Invalid cluster definition: {exc} "
        ) from exc
    except ClusterNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"{exc}") from exc
    except ClusterAccessForbidden as exc:
        raise web.HTTPForbidden(reason=f"{exc}") from exc


@routes.delete(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="delete_cluster_handler"
)
@login_required
@permission_required("clusters.delete")
async def delete_cluster_handler(request: web.Request) -> web.Response:
    path, _, _ = await extract_and_validate(request)
    user_id: UserID = request[RQT_USERID_KEY]
    try:
        await director_v2_api.delete_cluster(request.app, user_id, path["cluster_id"])
        return web.json_response(status=web.HTTPNoContent.status_code)
    except ClusterNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"{exc}") from exc
    except ClusterAccessForbidden as exc:
        raise web.HTTPForbidden(reason=f"{exc}") from exc
