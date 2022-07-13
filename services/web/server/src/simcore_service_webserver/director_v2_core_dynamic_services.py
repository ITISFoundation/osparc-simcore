import json
import logging
from typing import Optional

from aiohttp import web
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.users import UserID
from pydantic.types import PositiveInt
from servicelib.logging_utils import log_decorator
from servicelib.utils import logged_gather
from settings_library.utils_cli import create_json_encoder_wo_secrets
from yarl import URL

from .director_v2_core_base import DataType, request_director_v2
from .director_v2_exceptions import (
    ClusterDefinedPingError,
    ClusterPingError,
    DirectorServiceError,
)
from .director_v2_models import ClusterPing
from .director_v2_settings import DirectorV2Settings, get_plugin_settings

log = logging.getLogger(__name__)


#
# DYNAMIC SERVICES ----------------------
#
@log_decorator(logger=log)
async def run_dynamic_service(
    app: web.Application,
    user_id: PositiveInt,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
    request_dns: str,
    request_scheme: str,
    service_resources: ServiceResourcesDict,
) -> DataType:
    """
    Requests to run (i.e. create and start) a dynamic service:
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
        "service_resources": ServiceResourcesDictHelpers.create_jsonable(
            service_resources
        ),
    }

    headers = {
        "X-Dynamic-Sidecar-Request-DNS": request_dns,
        "X-Dynamic-Sidecar-Request-Scheme": request_scheme,
    }

    settings: DirectorV2Settings = get_plugin_settings(app)
    started_service = await request_director_v2(
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
async def get_dynamic_services(
    app: web.Application,
    user_id: Optional[PositiveInt] = None,
    project_id: Optional[str] = None,
) -> list[DataType]:
    params = {}
    if user_id:
        params["user_id"] = user_id
    if project_id:
        params["project_id"] = project_id

    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = settings.base_url / "dynamic_services"

    services = await request_director_v2(
        app, "GET", backend_url, params=params, expected_status=web.HTTPOk
    )

    assert isinstance(services, list)  # nosec
    return services


@log_decorator(logger=log)
async def get_dynamic_service_state(app: web.Application, node_uuid: str) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = settings.base_url / f"dynamic_services/{node_uuid}"

    service_state = await request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )

    assert isinstance(service_state, dict)  # nosec
    return service_state


@log_decorator(logger=log)
async def stop_dynamic_service(
    app: web.Application, service_uuid: str, save_state: bool = True
) -> None:
    # stopping a service can take a lot of time
    # bumping the stop command timeout to 1 hour
    # this will allow to sava bigger datasets from the services
    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
        app,
        "DELETE",
        url=(settings.base_url / f"dynamic_services/{service_uuid}").update_query(
            save_state="true" if save_state else "false",
        ),
        expected_status=web.HTTPNoContent,
        timeout=settings.DIRECTOR_V2_STOP_SERVICE_TIMEOUT,
    )


@log_decorator(logger=log)
async def stop_dynamic_services_in_project(
    app: web.Application,
    user_id: Optional[PositiveInt] = None,
    project_id: Optional[str] = None,
    save_state: bool = True,
) -> None:
    """Stops all services of either project_id or user_id in concurrently"""
    running_dynamic_services = await get_dynamic_services(
        app, user_id=user_id, project_id=project_id
    )

    services_to_stop = [
        stop_dynamic_service(
            app=app, service_uuid=service["service_uuid"], save_state=save_state
        )
        for service in running_dynamic_services
    ]
    await logged_gather(*services_to_stop)


# FIXME: ANE please unduplicate the 2 following calls!!!!
@log_decorator(logger=log)
async def retrieve(
    app: web.Application, service_uuid: str, port_keys: list[str]
) -> DataType:
    """Pulls data from connections to the dynamic service inputs"""
    settings: DirectorV2Settings = get_plugin_settings(app)
    result = await request_director_v2(
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
    app: web.Application, service_uuid: str, port_keys: list[str]
) -> None:
    # TODO: notice that this function is identical to retrieve except that it does NOT reaise
    settings: DirectorV2Settings = get_plugin_settings(app)
    body = {"port_keys": port_keys}

    try:
        await request_director_v2(
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
async def restart_dynamic_service(app: web.Application, node_uuid: str) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
        app,
        "POST",
        url=settings.base_url / f"dynamic_services/{node_uuid}:restart",
        expected_status=web.HTTPOk,
        timeout=settings.DIRECTOR_V2_RESTART_DYNAMIC_SERVICE_TIMEOUT,
    )


@log_decorator(logger=log)
async def update_dynamic_service_networks_in_project(
    app: web.Application, project_id: ProjectID
) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = (
        URL(settings.base_url) / f"dynamic_services/projects/{project_id}/-/networks"
    )
    await request_director_v2(
        app, "PATCH", backend_url, expected_status=web.HTTPNoContent
    )


async def ping_cluster(app: web.Application, cluster_ping: ClusterPing) -> None:
    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
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
    await request_director_v2(
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
