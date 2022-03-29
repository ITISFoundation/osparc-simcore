import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from uuid import UUID

import aiohttp
from aiohttp import ClientTimeout, web
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.users import UserID
from pydantic.types import PositiveInt
from servicelib.logging_utils import log_decorator
from servicelib.utils import logged_gather
from settings_library.utils_cli import create_json_encoder_wo_secrets
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random
from yarl import URL

from .director_v2_abc import AbstractProjectRunPolicy
from .director_v2_exceptions import (
    ClusterAccessForbidden,
    ClusterDefinedPingError,
    ClusterNotFoundError,
    ClusterPingError,
    DirectorServiceError,
)
from .director_v2_models import ClusterCreate, ClusterPatch, ClusterPing
from .director_v2_settings import (
    DirectorV2Settings,
    get_client_session,
    get_plugin_settings,
)

log = logging.getLogger(__name__)

_APP_DIRECTOR_V2_CLIENT_KEY = f"{__name__}.DirectorV2ApiClient"

SERVICE_HEALTH_CHECK_TIMEOUT = ClientTimeout(total=2, connect=1)  # type:ignore

DEFAULT_RETRY_POLICY = dict(
    wait=wait_random(0, 1),
    stop=stop_after_attempt(2),
    reraise=True,
    before_sleep=before_sleep_log(log, logging.WARNING),
)


DataType = Dict[str, Any]
DataBody = Union[DataType, List[DataType], None]


class DirectorV2ApiClient:
    def __init__(self, app: web.Application) -> None:
        self._app = app
        self._settings: DirectorV2Settings = get_plugin_settings(app)

    async def get(self, project_id: ProjectID, user_id: UserID) -> Dict[str, Any]:
        computation_task_out = await _request_director_v2(
            self._app,
            "GET",
            (self._settings.base_url / "computations" / f"{project_id}").with_query(
                user_id=user_id
            ),
            expected_status=web.HTTPOk,
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out

    async def start(self, project_id: ProjectID, user_id: UserID, **options) -> str:
        computation_task_out = await _request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations",
            expected_status=web.HTTPCreated,
            data={"user_id": user_id, "project_id": project_id, **options},
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out["id"]

    async def stop(self, project_id: ProjectID, user_id: UserID):
        await _request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations" / f"{project_id}:stop",
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
    on_error: Optional[
        Dict[int, Tuple[Type[DirectorServiceError], Dict[str, Any]]]
    ] = None,
    **kwargs,
) -> DataBody:
    if not on_error:
        on_error = {}
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

                    if response.status != expected_status.status_code:
                        if response.status in on_error:
                            exc, exc_ctx = on_error[response.status]
                            raise exc(
                                **exc_ctx, status=response.status, reason=f"{payload}"
                            )
                        raise DirectorServiceError(
                            status=response.status, reason=f"{payload}", url=url
                        )
                    return payload

    # TODO: enrich with https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
    except asyncio.TimeoutError as err:
        raise DirectorServiceError(
            status=web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 timed-out: {err}",
            url=url,
        ) from err

    except aiohttp.ClientError as err:
        raise DirectorServiceError(
            status=web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 service unexpected error {err}",
            url=url,
        ) from err
    log.error("Unexpected result calling %s, %s", f"{url=}", f"{method=}")
    raise DirectorServiceError(
        status=web.HTTPClientError.status_code,
        reason="Unexpected client error",
        url=url,
    )


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


async def is_healthy(app: web.Application) -> bool:
    try:
        session = get_client_session(app)
        settings: DirectorV2Settings = get_plugin_settings(app)
        health_check_url = settings.base_url.parent
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
    settings: DirectorV2Settings = get_plugin_settings(app)

    backend_url = settings.base_url / "computations"
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
async def is_pipeline_running(
    app: web.Application, user_id: PositiveInt, project_id: UUID
) -> Optional[bool]:

    # TODO: make it cheaper by /computations/{project_id}/state. First trial shows
    # that the efficiency gain is minimal but should be considered specially if the handler
    # gets heavier with time
    pipeline = await get_computation_task(app, user_id, project_id)
    if pipeline is None:
        # NOTE: at the time of this modification, error handling in `get_computation_task`
        # is still limited and any type of errors is transformed into a None. Therefore
        # at this point we cannot discern whether the pipeline is running or not.
        # In order to define the "UNKNOWN" state we return None, which in an
        # if statement casts to False
        return None

    return pipeline.state.is_running()


@log_decorator(logger=log)
async def get_computation_task(
    app: web.Application, user_id: UserID, project_id: ProjectID
) -> Optional[ComputationTask]:
    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = (settings.base_url / f"computations/{project_id}").update_query(
        user_id=int(user_id)
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
    settings: DirectorV2Settings = get_plugin_settings(app)

    backend_url = settings.base_url / f"computations/{project_id}"
    body = {"user_id": user_id, "force": True}

    # request to director-v2
    await _request_director_v2(
        app, "DELETE", backend_url, expected_status=web.HTTPNoContent, data=body
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

    settings: DirectorV2Settings = get_plugin_settings(app)
    started_service = await _request_director_v2(
        app,
        "POST",
        url=settings.base_url / "dynamic_services",
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

    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = settings.base_url / "dynamic_services"

    services = await _request_director_v2(
        app, "GET", backend_url, params=params, expected_status=web.HTTPOk
    )

    assert isinstance(services, list)  # nosec
    return services


@log_decorator(logger=log)
async def get_service_state(app: web.Application, node_uuid: str) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = settings.base_url / f"dynamic_services/{node_uuid}"

    service_state = await _request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )

    assert isinstance(service_state, dict)  # nosec
    return service_state


@log_decorator(logger=log)
async def stop_service(
    app: web.Application, service_uuid: str, save_state: bool = True
) -> None:
    # stopping a service can take a lot of time
    # bumping the stop command timeout to 1 hour
    # this will allow to sava bigger datasets from the services
    settings: DirectorV2Settings = get_plugin_settings(app)
    await _request_director_v2(
        app,
        "DELETE",
        url=(settings.base_url / f"dynamic_services/{service_uuid}").update_query(
            save_state="true" if save_state else "false",
        ),
        expected_status=web.HTTPNoContent,
        timeout=settings.DIRECTOR_V2_STOP_SERVICE_TIMEOUT,
    )


@log_decorator(logger=log)
async def stop_services(
    app: web.Application,
    user_id: Optional[PositiveInt] = None,
    project_id: Optional[str] = None,
    save_state: bool = True,
) -> None:
    """Stops all services of either project_id or user_id in concurrently"""
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


# FIXME: ANE please unduplicate the 2 following calls
@log_decorator(logger=log)
async def retrieve(
    app: web.Application, service_uuid: str, port_keys: List[str]
) -> DataType:
    """Pulls data from connections to the dynamic service inputs"""
    settings: DirectorV2Settings = get_plugin_settings(app)
    result = await _request_director_v2(
        app,
        "POST",
        url=settings.base_url / f"dynamic_services/{service_uuid}:retrieve",
        data={"port_keys": port_keys},
        timeout=settings.get_service_retrieve_timeout(),
    )
    assert isinstance(result, dict)  # nosec
    return result


@log_decorator(logger=log)
async def request_retrieve_dyn_service(
    app: web.Application, service_uuid: str, port_keys: List[str]
) -> None:
    # TODO: notice that this function is identical to retrieve except that it does NOT reaise
    settings: DirectorV2Settings = get_plugin_settings(app)
    body = {"port_keys": port_keys}

    try:
        await _request_director_v2(
            app,
            "POST",
            url=settings.base_url / f"dynamic_services/{service_uuid}:retrieve",
            data=body,
            timeout=settings.get_service_retrieve_timeout(),
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
async def restart(app: web.Application, node_uuid: str) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await _request_director_v2(
        app,
        "POST",
        url=settings.base_url / f"dynamic_services/{node_uuid}:restart",
        expected_status=web.HTTPOk,
        timeout=settings.DIRECTOR_V2_RESTART_DYNAMIC_SERVICE_TIMEOUT,
    )


@log_decorator(logger=log)
async def projects_networks_update(app: web.Application, project_id: ProjectID) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = (
        URL(settings.base_url) / f"dynamic_services/projects/{project_id}/-/networks"
    )
    await _request_director_v2(
        app, "PATCH", backend_url, expected_status=web.HTTPNoContent
    )


@log_decorator(logger=log)
async def create_cluster(
    app: web.Application, user_id: UserID, new_cluster: ClusterCreate
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    cluster = await _request_director_v2(
        app,
        "POST",
        url=(settings.base_url / "clusters").update_query(user_id=int(user_id)),
        expected_status=web.HTTPCreated,
        data=json.loads(
            new_cluster.json(
                by_alias=True,
                exclude_unset=True,
                encoder=create_json_encoder_wo_secrets(ClusterCreate),
            )
        ),
    )

    assert isinstance(cluster, dict)  # nosec
    return cluster


async def list_clusters(app: web.Application, user_id: UserID) -> List[DataType]:
    settings: DirectorV2Settings = get_plugin_settings(app)
    clusters = await _request_director_v2(
        app,
        "GET",
        url=(settings.base_url / "clusters").update_query(user_id=int(user_id)),
        expected_status=web.HTTPOk,
    )

    assert isinstance(clusters, list)  # nosec
    return clusters


async def get_cluster(
    app: web.Application, user_id: UserID, cluster_id: ClusterID
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    cluster = await _request_director_v2(
        app,
        "GET",
        url=(settings.base_url / f"clusters/{cluster_id}").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPOk,
        on_error={
            web.HTTPNotFound.status_code: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            web.HTTPForbidden.status_code: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )

    assert isinstance(cluster, dict)  # nosec
    return cluster


async def get_cluster_details(
    app: web.Application, user_id: UserID, cluster_id: ClusterID
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)

    cluster = await _request_director_v2(
        app,
        "GET",
        url=(settings.base_url / f"clusters/{cluster_id}/details").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPOk,
        on_error={
            web.HTTPNotFound.status_code: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            web.HTTPForbidden.status_code: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )

    assert isinstance(cluster, dict)  # nosec
    return cluster


async def update_cluster(
    app: web.Application,
    user_id: UserID,
    cluster_id: ClusterID,
    cluster_patch: ClusterPatch,
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    cluster = await _request_director_v2(
        app,
        "PATCH",
        url=(settings.base_url / f"clusters/{cluster_id}").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPOk,
        data=json.loads(
            cluster_patch.json(
                by_alias=True,
                exclude_unset=True,
                encoder=create_json_encoder_wo_secrets(ClusterPatch),
            )
        ),
        on_error={
            web.HTTPNotFound.status_code: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            web.HTTPForbidden.status_code: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )

    assert isinstance(cluster, dict)  # nosec
    return cluster


async def delete_cluster(
    app: web.Application, user_id: UserID, cluster_id: ClusterID
) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await _request_director_v2(
        app,
        "DELETE",
        url=(settings.base_url / f"clusters/{cluster_id}").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPNoContent,
        on_error={
            web.HTTPNotFound.status_code: (
                ClusterNotFoundError,
                {"cluster_id": cluster_id},
            ),
            web.HTTPForbidden.status_code: (
                ClusterAccessForbidden,
                {"cluster_id": cluster_id},
            ),
        },
    )


async def ping_cluster(app: web.Application, cluster_ping: ClusterPing) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await _request_director_v2(
        app,
        "POST",
        url=settings.base_url / "clusters:ping",
        expected_status=web.HTTPNoContent,
        data=json.loads(
            cluster_ping.json(
                by_alias=True,
                exclude_unset=True,
                encoder=create_json_encoder_wo_secrets(ClusterPing),
            )
        ),
        on_error={
            web.HTTPUnprocessableEntity.status_code: (
                ClusterPingError,
                {"endpoint": f"{cluster_ping.endpoint}"},
            )
        },
    )


async def ping_specific_cluster(
    app: web.Application, user_id: UserID, cluster_id: ClusterID
) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await _request_director_v2(
        app,
        "POST",
        url=(settings.base_url / f"clusters/{cluster_id}:ping").update_query(
            user_id=int(user_id)
        ),
        expected_status=web.HTTPNoContent,
        on_error={
            web.HTTPUnprocessableEntity.status_code: (
                ClusterDefinedPingError,
                {"cluster_id": f"{cluster_id}"},
            )
        },
    )
