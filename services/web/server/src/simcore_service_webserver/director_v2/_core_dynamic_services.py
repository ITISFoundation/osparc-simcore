""" Operations on dynamic-services

- This interface HIDES request/responses/exceptions to the director-v2 API service

"""

import logging
from contextlib import AsyncExitStack
from functools import partial

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeIDStr
from models_library.rabbitmq_messages import ProgressRabbitMessageProject, ProgressType
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import BaseModel
from pydantic.types import NonNegativeFloat, PositiveInt
from servicelib.common_headers import (
    X_DYNAMIC_SIDECAR_REQUEST_DNS,
    X_DYNAMIC_SIDECAR_REQUEST_SCHEME,
    X_SIMCORE_USER_AGENT,
)
from servicelib.logging_utils import log_decorator
from servicelib.progress_bar import ProgressBarData
from servicelib.rabbitmq import RabbitMQClient
from servicelib.utils import logged_gather
from yarl import URL

from ..rabbitmq import get_rabbitmq_client
from ._core_base import DataType, request_director_v2
from .exceptions import DirectorServiceError, ServiceWaitingForManualIntervention
from .settings import DirectorV2Settings, get_plugin_settings

_log = logging.getLogger(__name__)


class _Params(BaseModel):
    user_id: PositiveInt | None = None
    project_id: str | None = None


async def list_dynamic_services(
    app: web.Application,
    user_id: PositiveInt | None = None,
    project_id: str | None = None,
) -> list[DataType]:
    params = _Params(user_id=user_id, project_id=project_id)
    params_dict = params.dict(exclude_none=True)
    settings: DirectorV2Settings = get_plugin_settings(app)
    if params_dict:  # Update query doesnt work with no params to unwrap
        backend_url = (settings.base_url / "dynamic_services").update_query(
            **params_dict
        )
    else:
        backend_url = settings.base_url / "dynamic_services"

    services = await request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )

    if services is None:
        services = []
    assert isinstance(services, list)  # nosec
    return services


async def get_dynamic_service(app: web.Application, node_uuid: str) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = settings.base_url / f"dynamic_services/{node_uuid}"

    service_state = await request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )

    assert isinstance(service_state, dict)  # nosec
    return service_state


async def run_dynamic_service(
    *,
    app: web.Application,
    product_name: str,
    save_state: bool,
    user_id: PositiveInt,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
    request_dns: str,
    request_scheme: str,
    simcore_user_agent: str,
    service_resources: ServiceResourcesDict,
) -> DataType:
    """
    Requests to run (i.e. create and start) a dynamic service:
    - legacy services request is redirected to `director-v0`
    - dynamic-sidecar `director-v2` will handle the request
    """
    data = {
        "product_name": product_name,
        "can_save": save_state,
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
        X_DYNAMIC_SIDECAR_REQUEST_DNS: request_dns,
        X_DYNAMIC_SIDECAR_REQUEST_SCHEME: request_scheme,
        X_SIMCORE_USER_AGENT: simcore_user_agent,
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


async def stop_dynamic_service(
    app: web.Application,
    service_uuid: NodeIDStr,
    simcore_user_agent: str,
    *,
    save_state: bool = True,
    progress: ProgressBarData | None = None,
) -> None:
    """
    Stopping a service can take a lot of time
    bumping the stop command timeout to 1 hour
    this will allow to sava bigger datasets from the services
    """
    headers = {
        X_SIMCORE_USER_AGENT: simcore_user_agent,
    }
    settings: DirectorV2Settings = get_plugin_settings(app)

    async with AsyncExitStack() as stack:
        if progress:
            await stack.enter_async_context(progress)

        await request_director_v2(
            app,
            "DELETE",
            url=(settings.base_url / f"dynamic_services/{service_uuid}").update_query(
                can_save="true" if save_state else "false",
            ),
            headers=headers,
            expected_status=web.HTTPNoContent,
            timeout=settings.DIRECTOR_V2_STOP_SERVICE_TIMEOUT,
            on_error={
                web.HTTPConflict.status_code: (
                    ServiceWaitingForManualIntervention,
                    {"service_uuid": service_uuid},
                )
            },
        )


async def _post_progress_message(
    rabbitmq_client: RabbitMQClient,
    user_id: PositiveInt,
    project_id: str,
    progress_value: NonNegativeFloat,
) -> None:
    progress_message = ProgressRabbitMessageProject(
        user_id=user_id,
        project_id=ProjectID(project_id),
        progress_type=ProgressType.PROJECT_CLOSING,
        progress=progress_value,
    )

    await rabbitmq_client.publish(progress_message.channel_name, progress_message)


async def stop_dynamic_services_in_project(
    app: web.Application,
    user_id: PositiveInt,
    project_id: str,
    simcore_user_agent: str,
    save_state: bool = True,
) -> None:
    """Stops all dynamic services of either project_id or user_id in concurrently"""
    running_dynamic_services = await list_dynamic_services(
        app, user_id=user_id, project_id=project_id
    )

    async with AsyncExitStack() as stack:
        progress_bar = await stack.enter_async_context(
            ProgressBarData(
                steps=len(running_dynamic_services),
                progress_report_cb=partial(
                    _post_progress_message,
                    get_rabbitmq_client(app),
                    user_id,
                    project_id,
                ),
            )
        )

        services_to_stop = [
            stop_dynamic_service(
                app=app,
                service_uuid=service["service_uuid"],
                simcore_user_agent=simcore_user_agent,
                save_state=save_state,
                progress=progress_bar.sub_progress(1),
            )
            for service in running_dynamic_services
        ]

        await logged_gather(*services_to_stop)


# NOTE: ANE https://github.com/ITISFoundation/osparc-simcore/issues/3191
@log_decorator(logger=_log)
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


# NOTE: ANE https://github.com/ITISFoundation/osparc-simcore/issues/3191
# notice that this function is identical to retrieve except that it does NOT raises
@log_decorator(logger=_log)
async def request_retrieve_dyn_service(
    app: web.Application, service_uuid: str, port_keys: list[str]
) -> None:
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
        _log.warning(
            "Unable to call :retrieve endpoint on service %s, keys: [%s]: error: [%s:%s]",
            service_uuid,
            port_keys,
            exc.status,
            exc.reason,
        )


@log_decorator(logger=_log)
async def restart_dynamic_service(app: web.Application, node_uuid: str) -> None:
    """User restart the dynamic dynamic service started in the node_uuid

    NOTE that this operation will NOT restart all sidecar services
    (``simcore-service-dynamic-sidecar`` or ``reverse-proxy caddy`` services) but
    ONLY those containers in the compose-spec (i.e. the ones exposed to the user)
    """
    settings: DirectorV2Settings = get_plugin_settings(app)
    await request_director_v2(
        app,
        "POST",
        url=settings.base_url / f"dynamic_services/{node_uuid}:restart",
        expected_status=web.HTTPOk,
        timeout=settings.DIRECTOR_V2_RESTART_DYNAMIC_SERVICE_TIMEOUT,
    )


@log_decorator(logger=_log)
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
