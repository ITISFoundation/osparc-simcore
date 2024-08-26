import functools
import logging

from aiohttp import web
from models_library.api_schemas_webserver.clusters import (
    ClusterCreate,
    ClusterDetails,
    ClusterGet,
    ClusterPatch,
    ClusterPathParams,
    ClusterPing,
)
from models_library.users import UserID
from pydantic import BaseModel, Field, parse_obj_as
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.request_keys import RQT_USERID_KEY

from .._meta import api_version_prefix
from ..director_v2 import api as director_v2_api
from ..director_v2.exceptions import (
    ClusterAccessForbidden,
    ClusterNotFoundError,
    ClusterPingError,
    DirectorServiceError,
)
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response

_logger = logging.getLogger(__name__)


def _handle_cluster_exceptions(handler: Handler):
    # maps API exceptions to HTTP errors
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ClusterPingError as exc:
            raise web.HTTPUnprocessableEntity(reason=f"{exc}") from exc

        except ClusterNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except ClusterAccessForbidden as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

        except DirectorServiceError as exc:
            raise web.HTTPServiceUnavailable(reason=f"{exc}") from exc

    return wrapper


#
# API components/schemas
#


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]


#
# API handlers
#

routes = web.RouteTableDef()


@routes.post(f"/{api_version_prefix}/clusters", name="create_cluster")
@login_required
@permission_required("clusters.create")
@_handle_cluster_exceptions
async def create_cluster(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    new_cluster = await parse_request_body_as(ClusterCreate, request)

    created_cluster = await director_v2_api.create_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        new_cluster=new_cluster,
    )
    return envelope_json_response(created_cluster, web.HTTPCreated)


@routes.get(f"/{api_version_prefix}/clusters", name="list_clusters")
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def list_clusters(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)

    clusters = await director_v2_api.list_clusters(
        app=request.app,
        user_id=req_ctx.user_id,
    )
    assert parse_obj_as(list[ClusterGet], clusters) is not None  # nosec
    return envelope_json_response(clusters)


@routes.get(f"/{api_version_prefix}/clusters/{{cluster_id}}", name="get_cluster")
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def get_cluster(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ClusterPathParams, request)

    cluster = await director_v2_api.get_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=path_params.cluster_id,
    )
    assert parse_obj_as(ClusterGet, cluster) is not None  # nosec
    return envelope_json_response(cluster)


@routes.patch(f"/{api_version_prefix}/clusters/{{cluster_id}}", name="update_cluster")
@login_required
@permission_required("clusters.write")
@_handle_cluster_exceptions
async def update_cluster(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ClusterPathParams, request)
    cluster_patch = await parse_request_body_as(ClusterPatch, request)

    updated_cluster = await director_v2_api.update_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=path_params.cluster_id,
        cluster_patch=cluster_patch,
    )

    assert parse_obj_as(ClusterGet, updated_cluster) is not None  # nosec
    return envelope_json_response(updated_cluster)


@routes.delete(f"/{api_version_prefix}/clusters/{{cluster_id}}", name="delete_cluster")
@login_required
@permission_required("clusters.delete")
@_handle_cluster_exceptions
async def delete_cluster(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ClusterPathParams, request)

    await director_v2_api.delete_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=path_params.cluster_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(
    f"/{api_version_prefix}/clusters/{{cluster_id}}/details",
    name="get_cluster_details",
)
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def get_cluster_details(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ClusterPathParams, request)

    cluster_details = await director_v2_api.get_cluster_details(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=path_params.cluster_id,
    )
    assert parse_obj_as(ClusterDetails, cluster_details) is not None  # nosec
    return envelope_json_response(cluster_details)


@routes.post(f"/{api_version_prefix}/clusters:ping", name="ping_cluster")
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def ping_cluster(request: web.Request) -> web.Response:
    cluster_ping = await parse_request_body_as(ClusterPing, request)

    await director_v2_api.ping_cluster(
        app=request.app,
        cluster_ping=cluster_ping,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(
    f"/{api_version_prefix}/clusters/{{cluster_id}}:ping",
    name="ping_cluster_cluster_id",
)
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def ping_cluster_cluster_id(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ClusterPathParams, request)

    await director_v2_api.ping_specific_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=path_params.cluster_id,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
