import logging
from typing import Any, Dict, List, Optional, Set, Union
from uuid import UUID

from aiohttp import ClientError, ClientTimeout, web
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.settings.services_common import ServicesCommonSettings
from pydantic.types import NonNegativeInt, PositiveInt
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_responses import wrap_as_envelope
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)
from servicelib.logging_utils import log_decorator
from servicelib.utils import logged_gather
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


class DirectorServiceError(Exception):
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
) -> Dict:
    session = get_client_session(app)
    try:
        async with session.request(
            method, url, headers=headers, json=data, **kwargs
        ) as response:
            # sometimes director-v0 (via redirects) replies
            # in plain text
            payload: Union[Dict, str] = (
                await response.json()
                if response.content_type == "application/json"
                else await response.text()
            )

            if response.status != expected_status.status_code:
                raise DirectorServiceError(response.status, payload)

            return payload

    except TimeoutError as err:
        raise DirectorServiceError(
            web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 timed-out: {err}",
        ) from err
    except ClientError as err:
        raise DirectorServiceError(
            web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 service unexpected error {err}",
        ) from err


async def is_healthy(app: web.Application) -> bool:
    try:
        session = get_client_session(app)
        settings: Directorv2Settings = get_settings(app)
        health_check_url = URL(settings.endpoint).parent
        await session.get(
            url=health_check_url,
            ssl=False,
            raise_for_status=True,
            timeout=ClientTimeout(total=2, connect=1),
        )
        return True
    except (ClientError, TimeoutError) as err:
        # ClientResponseError, ClientConnectionError, ClientPayloadError, InValidURL
        log.warning("Director is NOT healthy: %s", err)
        return False


@log_decorator(logger=log)
async def create_or_update_pipeline(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> Dict[str, Any]:
    director2_settings: Directorv2Settings = get_settings(app)

    backend_url = URL(f"{director2_settings.endpoint}/computations")
    body = {"user_id": user_id, "project_id": f"{project_id}"}
    # request to director-v2
    try:
        computation_task_out = await _request_director_v2(
            app, "POST", backend_url, expected_status=web.HTTPCreated, data=body
        )
        return computation_task_out

    except DirectorServiceError as exc:
        log.error("could not create pipeline from project %s: %s", project_id, exc)


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
    except DirectorServiceError as exc:
        if exc.status == web.HTTPNotFound.status_code:
            # the pipeline might not exist and that is ok
            return
        log.warning("getting pipeline for project %s failed: %s.", project_id, exc)


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
            total=SERVICE_RETRIEVE_HTTP_TIMEOUT, connect=None, sock_connect=5
        )
        await _request_director_v2(
            app, "POST", backend_url, data=body, timeout=client_timeout
        )
    except DirectorServiceError as exc:
        log.warning(
            "Unable to call :retrieve endpoint on service %s, keys: [%s]: error: [%s:%s]",
            service_uuid,
            port_keys,
            exc.status,
            exc.reason,
        )


@log_decorator(logger=log)
async def start_service(
    app: web.Application,
    user_id: PositiveInt,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
    request_dns: str,
    request_scheme: str,
) -> Optional[Dict]:
    """
    Requests to start a service:
    - legacy services request is redirected to `director-v0`
    - dynamic-sidecar `director-v2` will handle the request
    """
    data = {
        "user_id": user_id,
        "project_id": project_id,
        "key": service_key,
        "version": service_version,
        "node_uuid": service_uuid,
        "basepath": f"/x/{service_uuid}",
    }

    headers = {
        "X-Dynamic-Sidecar-Request-DNS": request_dns,
        "X-Dynamic-Sidecar-Request-Scheme": request_scheme,
    }

    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = URL(director2_settings.endpoint) / "dynamic_services"

    return await _request_director_v2(
        app,
        "POST",
        backend_url,
        data=data,
        headers=headers,
        expected_status=web.HTTPCreated,
    )


@log_decorator(logger=log)
async def get_services(
    app: web.Application,
    user_id: Optional[PositiveInt] = None,
    project_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params = {}
    if user_id:
        params["user_id"] = user_id
    if project_id:
        params["project_id"] = project_id

    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = URL(director2_settings.endpoint) / "dynamic_services"

    return await _request_director_v2(
        app, "GET", backend_url, params=params, expected_status=web.HTTPOk
    )


@log_decorator(logger=log)
async def stop_service(
    app: web.Application, service_uuid: str, save_state: Optional[bool] = True
) -> None:
    # stopping a service can take a lot of time
    # bumping the stop command timeout to 1 hour
    # this will allow to sava bigger datasets from the services
    timeout = ServicesCommonSettings().webserver_director_stop_service_timeout

    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = (
        URL(director2_settings.endpoint) / "dynamic_services" / f"{service_uuid}"
    ).update_query(
        save_state="true" if save_state else "false",
    )
    return await _request_director_v2(
        app, "DELETE", backend_url, expected_status=web.HTTPNoContent, timeout=timeout
    )


@log_decorator(logger=log)
async def list_running_dynamic_services(
    app: web.Application, user_id: PositiveInt, project_id: ProjectID
) -> List[Dict[str, str]]:
    """
    Retruns the running dynamic services from director-v0 and director-v2
    """
    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = (URL(director2_settings.endpoint) / "dynamic_services").update_query(
        user_id=user_id, project_id=project_id
    )

    return await _request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )


@log_decorator(logger=log)
async def stop_services(
    app: web.Application,
    user_id: Optional[PositiveInt] = None,
    project_id: Optional[str] = None,
    save_state: Optional[bool] = True,
) -> None:
    """Stops all services in parallel"""
    running_dynamic_services = await get_services(
        app, user_id=user_id, project_id=project_id
    )

    services_to_stop = [
        stop_service(
            app=app, service_uuid=service["service_uuid"], save_state=save_state
        )
        for service in running_dynamic_services
    ]
    await logged_gather(*services_to_stop)


@log_decorator(logger=log)
async def get_service_state(app: web.Application, node_uuid: str) -> Dict:
    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = URL(director2_settings.endpoint) / "dynamic_services" / f"{node_uuid}"
    return await _request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )


@log_decorator(logger=log)
async def retrieve(
    app: web.Application, node_uuid: str, port_keys: List[str]
) -> Dict[str, Dict[str, int]]:
    # when triggering retrieve endpoint
    # this will allow to sava bigger datasets from the services
    timeout = ServicesCommonSettings().storage_service_upload_download_timeout

    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = (
        URL(director2_settings.endpoint) / "dynamic_services" / f"{node_uuid}:retrieve"
    )
    body = dict(port_keys=port_keys)
    return await _request_director_v2(
        app, "POST", backend_url, expected_status=web.HTTPOk, data=body, timeout=timeout
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
