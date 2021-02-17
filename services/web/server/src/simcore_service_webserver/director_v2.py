import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID

from aiohttp import ClientTimeout, web
from models_library.projects_pipeline import ComputationTask
from pydantic.types import PositiveInt
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.logging_utils import log_decorator
from servicelib.rest_responses import wrap_as_envelope
from servicelib.rest_routing import iter_path_operations, map_handlers_with_operations
from yarl import URL

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


async def _request_director_v2(
    app: web.Application,
    method: str,
    url: URL,
    expected_status: web.HTTPSuccessful = web.HTTPOk,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    **kwargs,
) -> Tuple[Dict, int]:
    session = get_client_session(app)
    try:
        async with session.request(
            method, url, headers=headers, json=data, **kwargs
        ) as resp:
            if resp.status != expected_status.status_code:
                # in some cases the director answers with plain text
                payload: Union[Dict, str] = (
                    await resp.json()
                    if resp.content_type == "application/json"
                    else await resp.text()
                )
                raise _DirectorServiceError(resp.status, payload)

            payload: Dict = await resp.json()
            return payload

    except TimeoutError as err:
        raise web.HTTPServiceUnavailable(
            reason="director service is currently unavailable"
        ) from err


@log_decorator(logger=log)
async def create_or_update_pipeline(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> Dict[str, Any]:
    director2_settings: Directorv2Settings = get_settings(app)

    backend_url = URL(f"{director2_settings.endpoint}/computations")
    body = {"user_id": user_id, "project_id": str(project_id)}
    # request to director-v2
    try:
        computation_task_out = await _request_director_v2(
            app, "POST", backend_url, expected_status=web.HTTPCreated, data=body
        )
        return computation_task_out

    except _DirectorServiceError:
        log.error("could not create pipeline from project %s", project_id)


@log_decorator(logger=log)
async def get_computation_task(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> Optional[ComputationTask]:
    director2_settings: Directorv2Settings = get_settings(app)

    backend_url = URL(
        f"{director2_settings.endpoint}/computations/{project_id}"
    ).update_query(user_id=user_id)

    # request to director-v2
    try:
        computation_task_out_dict = await _request_director_v2(
            app, "GET", backend_url, expected_status=web.HTTPAccepted
        )
        task_out = ComputationTask.parse_obj(computation_task_out_dict)
        return task_out
    except _DirectorServiceError:
        log.warning(
            "getting pipeline for project %s failed.",
            project_id,
        )


@log_decorator(logger=log)
async def delete_pipeline(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> None:
    director2_settings: Directorv2Settings = get_settings(app)

    backend_url = URL(f"{director2_settings.endpoint}/computations/{project_id}")
    body = {"user_id": user_id, "force": True}

    # request to director-v2
    await _request_director_v2(
        app, "DELETE", backend_url, expected_status=web.HTTPNoContent, data=body
    )


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
    if request.can_read_body:
        body = await request.json()
        subgraph = body.get("subgraph")
        force_restart = body.get("force_restart")

    backend_url = URL(f"{director2_settings.endpoint}/computations")
    log.debug("Redirecting '%s' -> '%s'", request.url, backend_url)
    body = {
        "user_id": user_id,
        "project_id": project_id,
        "start_pipeline": True,
        "subgraph": list(subgraph),  # sets are not natively json serializable
        "force_restart": force_restart,
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
    except _DirectorServiceError as exc:
        return web.json_response(
            data=wrap_as_envelope(error=exc.reason), status=exc.status
        )


SERVICE_RETRIEVE_HTTP_TIMEOUT = 60 * 60  # 1 hour


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
        client_timeout = ClientTimeout(
            total=SERVICE_RETRIEVE_HTTP_TIMEOUT, connect=5, sock_connect=5
        )
        await _request_director_v2(
            app, "POST", backend_url, data=body, timeout=client_timeout
        )
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
