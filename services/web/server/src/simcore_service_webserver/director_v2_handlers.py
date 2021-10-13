import logging
from typing import Set

from aiohttp import web
from pydantic.types import NonNegativeInt
from servicelib.aiohttp.rest_responses import create_error_response, get_http_error
from servicelib.json_serialization import json_dumps
from servicelib.logging_utils import log_decorator
from yarl import URL

from ._meta import api_version_prefix as VTAG
from .director_v2_core import DirectorServiceError, _request_director_v2
from .director_v2_settings import Directorv2Settings, get_settings
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required

log = logging.getLogger(__file__)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/computation/pipeline/{{project_id}}:start")
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
@log_decorator(logger=log)
async def start_pipeline(request: web.Request) -> web.Response:
    director2_settings: Directorv2Settings = get_settings(request.app)

    user_id = request[RQT_USERID_KEY]
    project_id = request.match_info.get("project_id", None)
    subgraph: Set[str] = set()
    force_restart = False
    cluster_id: NonNegativeInt = 0
    if request.can_read_body:
        body = await request.json()
        subgraph = body.get("subgraph")
        force_restart = body.get("force_restart")
        cluster_id = body.get("cluster_id")

    backend_url = URL(f"{director2_settings.endpoint}/computations")
    log.debug("Redirecting '%s' -> '%s'", request.url, backend_url)
    body = {
        "user_id": user_id,
        "project_id": project_id,
        "start_pipeline": True,
        "subgraph": list(subgraph),  # sets are not natively json serializable
        "force_restart": force_restart,
        "cluster_id": cluster_id,
    }

    # request to director-v2
    try:
        computation_task_out = await _request_director_v2(
            request.app, "POST", backend_url, expected_status=web.HTTPCreated, data=body
        )
        data = {"pipeline_id": computation_task_out["id"]}

        return web.json_response(
            data={"data": data},
            status=web.HTTPCreated.status_code,
            dumps=json_dumps,
        )
    except DirectorServiceError as exc:
        return create_error_response(
            exc,
            reason=exc.reason,
            http_error_cls=get_http_error(exc.status) or web.HTTPServiceUnavailable,
        )


@routes.post(f"/{VTAG}/computation/pipeline/{{project_id}}:stop")
@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
@log_decorator(logger=log)
async def stop_pipeline(request: web.Request) -> web.Response:
    director2_settings: Directorv2Settings = get_settings(request.app)

    user_id = request[RQT_USERID_KEY]
    project_id = request.match_info.get("project_id", None)

    backend_url = URL(f"{director2_settings.endpoint}/computations/{project_id}:stop")
    log.debug("Redirecting '%s' -> '%s'", request.url, backend_url)
    body = {"user_id": user_id}

    # request to director-v2
    try:
        await _request_director_v2(
            request.app,
            "POST",
            backend_url,
            expected_status=web.HTTPAccepted,
            data=body,
        )

        raise web.HTTPNoContent()
    except DirectorServiceError as exc:
        return create_error_response(
            exc,
            reason=exc.reason,
            http_error_cls=get_http_error(exc.status) or web.HTTPServiceUnavailable,
        )
