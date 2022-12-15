import functools
import logging

from aiohttp import web
from models_library.clusters import ClusterID
from models_library.users import UserID
from pydantic import BaseModel, Extra, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.json_serialization import json_dumps

from .. import director_v2_api
from .._meta import api_version_prefix
from ..director_v2_exceptions import (
    ClusterAccessForbidden,
    ClusterNotFoundError,
    ClusterPingError,
    DirectorServiceError,
)
from ..director_v2_models import ClusterCreate, ClusterPatch, ClusterPing
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_decorators import permission_required

logger = logging.getLogger(__name__)


def _handle_cluster_exceptions(handler: Handler):
    # maps API exceptions to HTTP errors
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.Response:
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
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)


class _ClusterPathParams(BaseModel):
    cluster_id: ClusterID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


#
# API handlers
#

routes = web.RouteTableDef()


@routes.post(f"/{api_version_prefix}/clusters", name="create_cluster_handler")
@login_required
@permission_required("clusters.create")
@_handle_cluster_exceptions
async def create_cluster_handler(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    new_cluster = await parse_request_body_as(ClusterCreate, request)

    created_cluster = await director_v2_api.create_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        new_cluster=new_cluster,
    )
    return web.json_response(
        data={"data": created_cluster},
        status=web.HTTPCreated.status_code,
        dumps=json_dumps,
    )


@routes.get(f"/{api_version_prefix}/clusters", name="list_clusters_handler")
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def list_clusters_handler(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)

    data = await director_v2_api.list_clusters(
        app=request.app,
        user_id=req_ctx.user_id,
    )
    return web.json_response(data={"data": data}, dumps=json_dumps)


@routes.get(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="get_cluster_handler"
)
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def get_cluster_handler(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ClusterPathParams, request)

    cluster = await director_v2_api.get_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=query_params.cluster_id,
    )
    return web.json_response(data={"data": cluster}, dumps=json_dumps)


@routes.get(
    f"/{api_version_prefix}/clusters/{{cluster_id}}/details",
    name="get_cluster_details_handler",
)
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def get_cluster_details_handler(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ClusterPathParams, request)

    cluster_details = await director_v2_api.get_cluster_details(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=query_params.cluster_id,
    )
    return web.json_response(data={"data": cluster_details}, dumps=json_dumps)


@routes.patch(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="update_cluster_handler"
)
@login_required
@permission_required("clusters.write")
@_handle_cluster_exceptions
async def update_cluster_handler(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ClusterPathParams, request)
    cluster_patch = await parse_request_body_as(ClusterPatch, request)

    updated_cluster = await director_v2_api.update_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=query_params.cluster_id,
        cluster_patch=cluster_patch,
    )
    return web.json_response(data={"data": updated_cluster}, dumps=json_dumps)


@routes.delete(
    f"/{api_version_prefix}/clusters/{{cluster_id}}", name="delete_cluster_handler"
)
@login_required
@permission_required("clusters.delete")
@_handle_cluster_exceptions
async def delete_cluster_handler(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ClusterPathParams, request)

    await director_v2_api.delete_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=query_params.cluster_id,
    )
    return web.json_response(status=web.HTTPNoContent.status_code)


@routes.post(f"/{api_version_prefix}/clusters:ping", name="ping_cluster_handler")
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def ping_cluster_handler(request: web.Request) -> web.Response:
    cluster_ping = await parse_request_body_as(ClusterPing, request)

    await director_v2_api.ping_cluster(
        app=request.app,
        cluster_ping=cluster_ping,
    )
    return web.json_response(status=web.HTTPNoContent.status_code)


@routes.post(
    f"/{api_version_prefix}/clusters/{{cluster_id}}:ping",
    name="ping_cluster_cluster_id_handler",
)
@login_required
@permission_required("clusters.read")
@_handle_cluster_exceptions
async def ping_cluster_cluster_id_handler(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_ClusterPathParams, request)

    await director_v2_api.ping_specific_cluster(
        app=request.app,
        user_id=req_ctx.user_id,
        cluster_id=query_params.cluster_id,
    )
    return web.json_response(status=web.HTTPNoContent.status_code)
