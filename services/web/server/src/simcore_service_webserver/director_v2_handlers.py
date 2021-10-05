import logging
from typing import Set

from aiohttp import web
from pydantic.types import NonNegativeInt
from servicelib.aiohttp.rest_responses import wrap_as_envelope
from servicelib.logging_utils import log_decorator
from yarl import URL

from ._meta import api_version_prefix as vtag
from .director_v2_core import DirectorServiceError, _request_director_v2
from .director_v2_settings import Directorv2Settings, get_settings
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required

log = logging.getLogger(__file__)


routes = web.RouteTableDef()


# TODO: replace by @routes.post(f"/{vtag}/projects/{{project_uuid}}/workbench:start")
@routes.post(f"/{vtag}/computation/pipeline/{{project_uuid}}:start")
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
            data=wrap_as_envelope(data=data), status=web.HTTPCreated.status_code
        )
    except DirectorServiceError as exc:
        return web.json_response(
            data=wrap_as_envelope(error=exc.reason), status=exc.status
        )


# TODO: replace by @routes.post(f"/{vtag}/projects/{{project_uuid}}/workbench:start")
@routes.post(f"/{vtag}/computation/pipeline/{{project_uuid}}:stop")
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
        data = {}
        return web.json_response(
            data=wrap_as_envelope(data=data), status=web.HTTPNoContent.status_code
        )
    except DirectorServiceError as exc:
        return web.json_response(
            data=wrap_as_envelope(error=exc.reason), status=exc.status
        )
