import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from uuid import UUID

import aiohttp
from aiohttp import ClientTimeout, web
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.settings.services_common import ServicesCommonSettings
from models_library.users import UserID
from pydantic.types import PositiveInt
from servicelib.logging_utils import log_decorator
from servicelib.utils import logged_gather
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random
from yarl import URL

from .director_v2_abc import AbstractProjectRunPolicy
from .director_v2_settings import Directorv2Settings, get_client_session, get_settings

log = logging.getLogger(__file__)

_APP_DIRECTOR_V2_CLIENT_KEY = f"{__name__}.DirectorV2ApiClient"

SERVICE_HEALTH_CHECK_TIMEOUT = ClientTimeout(total=2, connect=1)  # type:ignore
SERVICE_RETRIEVE_HTTP_TIMEOUT = ClientTimeout(
    total=60 * 60, connect=None, sock_connect=5  # type:ignore
)
DEFAULT_RETRY_POLICY = dict(
    wait=wait_random(0, 1),
    stop=stop_after_attempt(2),
    reraise=True,
    before_sleep=before_sleep_log(log, logging.WARNING),
)


DataType = Dict[str, Any]
DataBody = Union[DataType, List[DataType], None]

# base/ERRORS ------------------------------------------------


class DirectorServiceError(Exception):
    """Basic exception for errors raised by director"""

    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(f"forwarded call failed with status {status}, reason {reason}")


# base/HELPERS ------------------------------------------------


class DirectorV2ApiClient:
    def __init__(self, app: web.Application) -> None:
        self._app = app
        self._settings: Directorv2Settings = get_settings(app)
        self._base_url = URL(self._settings.endpoint)

    async def start(self, project_id: ProjectID, user_id: UserID, **options) -> str:
        computation_task_out = await _request_director_v2(
            self._app,
            "POST",
            self._base_url / "computations",
            expected_status=web.HTTPCreated,
            data={"user_id": user_id, "project_id": project_id, **options},
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out["id"]

    async def stop(self, project_id: ProjectID, user_id: UserID):
        await _request_director_v2(
            self._app,
            "POST",
            self._base_url / "computations" / f"{project_id}:stop",
            expected_status=web.HTTPAccepted,
            data={"user_id": user_id},
        )


def get_client(app: web.Application) -> Optional[DirectorV2ApiClient]:
    return app.get(_APP_DIRECTOR_V2_CLIENT_KEY)


def set_client(app: web.Application, obj: DirectorV2ApiClient):
    app[_APP_DIRECTOR_V2_CLIENT_KEY] = obj


async def _request_director_v2(
    app: web.Application,
    method: str,
    url: URL,
    expected_status: Type[web.HTTPSuccessful] = web.HTTPOk,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Any] = None,
    **kwargs,
) -> DataBody:

    try:
        async for attempt in AsyncRetrying(**DEFAULT_RETRY_POLICY):
            with attempt:
                session = get_client_session(app)
                async with session.request(
                    method, url, headers=headers, json=data, **kwargs
                ) as response:
                    payload = (
                        await response.json()
                        if response.content_type == "application/json"
                        else await response.text()
                    )
                    # NOTE:
                    # - `sometimes director-v0` (via redirects) replies
                    #   in plain text and this is considered an error
                    # - `director-v2` and `director-v0` can reply with 204 no content
                    if response.status != expected_status.status_code or isinstance(
                        payload, str
                    ):
                        raise DirectorServiceError(response.status, reason=f"{payload}")
                    return payload

    # TODO: enrich with https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
    except asyncio.TimeoutError as err:
        raise DirectorServiceError(
            web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 timed-out: {err}",
        ) from err

    except aiohttp.ClientError as err:
        raise DirectorServiceError(
            web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 service unexpected error {err}",
        ) from err
    raise DirectorServiceError(
        web.HTTPClientError.status_code, reason="Unexpected client error"
    )


# POLICY ------------------------------------------------
class DefaultProjectRunPolicy(AbstractProjectRunPolicy):
    # pylint: disable=unused-argument

    async def get_runnable_projects_ids(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> List[ProjectID]:
        return [
            project_uuid,
        ]

    async def get_or_create_runnable_projects(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> Tuple[List[ProjectID], List[int]]:
        """
        Returns ids and refid of projects that can run
        If project_uuid is a std-project, then it returns itself
        If project_uuid is a meta-project, then it returns iterations
        """
        return (
            [
                project_uuid,
            ],
            [],
        )


# calls to director-v2 API ------------------------------------------------


async def is_healthy(app: web.Application) -> bool:
    try:
        session = get_client_session(app)
        settings: Directorv2Settings = get_settings(app)
        health_check_url = URL(settings.endpoint).parent
        await session.get(
            url=health_check_url,
            ssl=False,
            raise_for_status=True,
            timeout=SERVICE_HEALTH_CHECK_TIMEOUT,
        )
        return True
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        # SEE https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
        log.warning("Director is NOT healthy: %s", err)
        return False


@log_decorator(logger=log)
async def create_or_update_pipeline(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> Optional[DataType]:
    settings: Directorv2Settings = get_settings(app)

    backend_url = URL(f"{settings.endpoint}/computations")
    body = {"user_id": user_id, "project_id": f"{project_id}"}
    # request to director-v2
    try:
        computation_task_out = await _request_director_v2(
            app, "POST", backend_url, expected_status=web.HTTPCreated, data=body
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out

    except DirectorServiceError as exc:
        log.error("could not create pipeline from project %s: %s", project_id, exc)


@log_decorator(logger=log)
async def get_computation_task(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> Optional[ComputationTask]:
    settings: Directorv2Settings = get_settings(app)
    backend_url = URL(f"{settings.endpoint}/computations/{project_id}").update_query(
        user_id=user_id
    )

    # request to director-v2
    try:
        computation_task_out_dict = await _request_director_v2(
            app, "GET", backend_url, expected_status=web.HTTPAccepted
        )
        task_out = ComputationTask.parse_obj(computation_task_out_dict)
        log.debug("found computation task: %s", f"{task_out=}")
        return task_out
    except DirectorServiceError as exc:
        if exc.status == web.HTTPNotFound.status_code:
            # the pipeline might not exist and that is ok
            return
        log.warning(
            "getting pipeline for project %s failed: %s.", f"{project_id=}", exc
        )


@log_decorator(logger=log)
async def delete_pipeline(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> None:
    settings: Directorv2Settings = get_settings(app)

    backend_url = URL(f"{settings.endpoint}/computations/{project_id}")
    body = {"user_id": user_id, "force": True}

    # request to director-v2
    await _request_director_v2(
        app, "DELETE", backend_url, expected_status=web.HTTPNoContent, data=body
    )


@log_decorator(logger=log)
async def request_retrieve_dyn_service(
    app: web.Application, service_uuid: str, port_keys: List[str]
) -> None:
    settings: Directorv2Settings = get_settings(app)
    backend_url = URL(f"{settings.endpoint}/dynamic_services/{service_uuid}:retrieve")
    body = {"port_keys": port_keys}

    try:
        await _request_director_v2(
            app, "POST", backend_url, data=body, timeout=SERVICE_RETRIEVE_HTTP_TIMEOUT
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
) -> DataType:
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

    settings: Directorv2Settings = get_settings(app)
    backend_url = URL(settings.endpoint) / "dynamic_services"

    started_service = await _request_director_v2(
        app,
        "POST",
        backend_url,
        data=data,
        headers=headers,
        expected_status=web.HTTPCreated,
    )

    assert isinstance(started_service, dict)  # nosec
    return started_service


@log_decorator(logger=log)
async def get_services(
    app: web.Application,
    user_id: Optional[PositiveInt] = None,
    project_id: Optional[str] = None,
) -> List[DataType]:
    params = {}
    if user_id:
        params["user_id"] = user_id
    if project_id:
        params["project_id"] = project_id

    settings: Directorv2Settings = get_settings(app)
    backend_url = URL(settings.endpoint) / "dynamic_services"

    services = await _request_director_v2(
        app, "GET", backend_url, params=params, expected_status=web.HTTPOk
    )

    assert isinstance(services, list)  # nosec
    return services


@log_decorator(logger=log)
async def stop_service(
    app: web.Application, service_uuid: str, save_state: Optional[bool] = True
) -> None:
    # stopping a service can take a lot of time
    # bumping the stop command timeout to 1 hour
    # this will allow to sava bigger datasets from the services
    timeout = ServicesCommonSettings().webserver_director_stop_service_timeout

    settings: Directorv2Settings = get_settings(app)
    backend_url = (
        URL(settings.endpoint) / "dynamic_services" / f"{service_uuid}"
    ).update_query(
        save_state="true" if save_state else "false",
    )
    await _request_director_v2(
        app, "DELETE", backend_url, expected_status=web.HTTPNoContent, timeout=timeout
    )


@log_decorator(logger=log)
async def list_running_dynamic_services(
    app: web.Application, user_id: PositiveInt, project_id: ProjectID
) -> List[DataType]:
    """
    Retruns the running dynamic services from director-v0 and director-v2
    """
    settings: Directorv2Settings = get_settings(app)
    url = URL(settings.endpoint) / "dynamic_services"
    backend_url = url.with_query(user_id=str(user_id), project_id=str(project_id))

    services = await _request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )

    assert isinstance(services, list)  # nosec
    return services


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
async def get_service_state(app: web.Application, node_uuid: str) -> DataType:
    settings: Directorv2Settings = get_settings(app)
    backend_url = URL(settings.endpoint) / "dynamic_services" / f"{node_uuid}"

    service_state = await _request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )

    assert isinstance(service_state, dict)  # nosec
    return service_state


@log_decorator(logger=log)
async def retrieve(
    app: web.Application, node_uuid: str, port_keys: List[str]
) -> DataBody:
    # when triggering retrieve endpoint
    # this will allow to sava bigger datasets from the services
    timeout = ServicesCommonSettings().storage_service_upload_download_timeout

    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = (
        URL(director2_settings.endpoint) / "dynamic_services" / f"{node_uuid}:retrieve"
    )
    body = dict(port_keys=port_keys)

    retry_result = await _request_director_v2(
        app,
        "POST",
        backend_url,
        expected_status=web.HTTPOk,
        data=body,
        timeout=timeout,
    )

    assert isinstance(retry_result, dict)  # nosec
    return retry_result


@log_decorator(logger=log)
async def restart(app: web.Application, node_uuid: str) -> None:
    # when triggering retrieve endpoint
    # this will allow to sava bigger datasets from the services
    timeout = ServicesCommonSettings().restart_containers_timeout

    director2_settings: Directorv2Settings = get_settings(app)
    backend_url = (
        URL(director2_settings.endpoint) / "dynamic_services" / f"{node_uuid}:restart"
    )

    await _request_director_v2(
        app,
        "POST",
        backend_url,
        expected_status=web.HTTPOk,
        timeout=timeout,
    )
