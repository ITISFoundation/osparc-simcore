import logging
from asyncio import CancelledError
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from aiohttp import web
from pydantic.types import PositiveInt
from yarl import URL

from models_library.projects_state import RunningState
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.logging_utils import log_decorator
from servicelib.rest_responses import wrap_as_envelope
from servicelib.rest_routing import iter_path_operations, map_handlers_with_operations

from .director_v2_settings import (
    CONFIG_SECTION_NAME,
    Directorv2Settings,
    create_settings,
    get_client_session,
    get_settings,
)
from .login.decorators import RQT_USERID_KEY, login_required
from .rest_config import APP_OPENAPI_SPECS_KEY
from .security_decorators import permission_required

log = logging.getLogger(__file__)


class _DirectorServiceError(Exception):
    """Basic exception for errors raised by director"""

    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(f"forwarded call failed with status {status}, reason {reason}")


@log_decorator(logger=log)
async def _request_director_v2(
    app: web.Application,
    method: str,
    url: URL,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
) -> Tuple[Dict, int]:
    session = get_client_session(app)
    try:
        async with session.request(method, url, headers=headers, json=data) as resp:
            payload: Dict = await resp.json()
            if resp.status >= 400:
                raise _DirectorServiceError(resp.status, payload)
            return (payload, resp.status)

    except (CancelledError, TimeoutError) as err:
        raise web.HTTPServiceUnavailable(
            reason="director service is currently unavailable"
        ) from err


@log_decorator(logger=log)
async def create_or_update_pipeline(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> Optional[Dict[str, Any]]:
    director2_settings: Directorv2Settings = get_settings(app)

    backend_url = URL(f"{director2_settings.endpoint}/computations")
    body = {"user_id": user_id, "project_id": str(project_id)}
    # request to director-v2
    try:
        computation_task_out, _ = await _request_director_v2(
            app, "POST", backend_url, data=body
        )
        return computation_task_out

    except _DirectorServiceError:
        log.error("could not create pipeline from project %s", project_id)


@log_decorator(logger=log)
async def get_pipeline_state(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> RunningState:
    director2_settings: Directorv2Settings = get_settings(app)

    backend_url = URL(
        f"{director2_settings.endpoint}/computations/{project_id}"
    ).update_query(user_id=user_id)

    # request to director-v2
    try:
        computation_task_out, _ = await _request_director_v2(app, "GET", backend_url)
    except _DirectorServiceError:
        log.warning(
            "getting pipeline state for project %s failed. state is then %s",
            project_id,
            RunningState.UNKNOWN,
        )
        return RunningState.UNKNOWN

    return RunningState(computation_task_out["state"])


@log_decorator(logger=log)
async def delete_pipeline(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> None:
    director2_settings: Directorv2Settings = get_settings(app)

    backend_url = URL(f"{director2_settings.endpoint}/computations/{project_id}")
    body = {"user_id": user_id, "force": True}

    # request to director-v2
    await _request_director_v2(app, "DELETE", backend_url, data=body)


@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
@log_decorator(logger=log)
async def start_pipeline(request: web.Request) -> web.Response:
    director2_settings: Directorv2Settings = get_settings(request.app)

    user_id = request[RQT_USERID_KEY]
    project_id = request.match_info.get("project_id", None)
    subgraph: Set[str] = set()
    if request.can_read_body:
        body = await request.json()
        subgraph = body.get("subgraph")

    backend_url = URL(f"{director2_settings.endpoint}/computations")
    log.debug("Redirecting '%s' -> '%s'", request.url, backend_url)
    body = {
        "user_id": user_id,
        "project_id": project_id,
        "start_pipeline": True,
        "subgraph": subgraph,
    }

    # request to director-v2
    try:
        computation_task_out, resp_status = await _request_director_v2(
            request.app, "POST", backend_url, data=body
        )
        data = {"pipeline_id": computation_task_out["id"]}

        return web.json_response(data=wrap_as_envelope(data=data), status=resp_status)
    except _DirectorServiceError as exc:
        return web.json_response(
            data=wrap_as_envelope(error=exc.reason), status=exc.status
        )


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
        _, resp_status = await _request_director_v2(
            request.app, "POST", backend_url, data=body
        )
        data = {}
        # director responds with a 202
        if resp_status != web.HTTPAccepted.status_code:
            raise _DirectorServiceError(
                resp_status, "Unexpected response from director-v2"
            )
        return web.json_response(
            data=wrap_as_envelope(data=data), status=web.HTTPNoContent.status_code
        )
    except _DirectorServiceError as exc:
        return web.json_response(
            data=wrap_as_envelope(error=exc.reason), status=exc.status
        )


@log_decorator(logger=log)
async def request_retrieve_dyn_service(
    app: web.Application, service_uuid: str, port_keys: List[str]
) -> None:
    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = URL(
        f"{director2_settings.endpoint}/dynamic_services/{service_uuid}:retrieve"
    )
    body = {"port_keys": port_keys}

    try:
        # request to director-v2
        await _request_director_v2(app, "POST", backend_url, data=body)
    except _DirectorServiceError as exc:
        log.warning(
            "Unable to call :retrieve endpoint on service %s, keys: [%s]: error: [%s:%s]",
            service_uuid,
            port_keys,
            exc.status,
            exc.reason,
        )


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    config_section=CONFIG_SECTION_NAME,
    depends=["simcore_service_webserver.rest"],
    logger=log,
)
def setup_director_v2(app: web.Application):
    # create settings and injects in app
    create_settings(app)

    if not APP_OPENAPI_SPECS_KEY in app:
        log.warning(
            "rest submodule not initialised? computation routes will not be defined!"
        )
        return

    specs = app[APP_OPENAPI_SPECS_KEY]
    # bind routes with handlers
    routes = map_handlers_with_operations(
        {
            "start_pipeline": start_pipeline,
            "stop_pipeline": stop_pipeline,
        },
        filter(lambda o: "computation" in o[1], iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(routes)
