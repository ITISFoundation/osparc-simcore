""" Operations on dynamic-services

- This interface HIDES request/responses/exceptions to the director-v2 API service

"""

import logging

from aiohttp import web
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.projects import ProjectID
from models_library.services import ServicePortKey
from pydantic import BaseModel, NonNegativeInt, TypeAdapter
from pydantic.types import PositiveInt
from servicelib.logging_utils import log_decorator
from yarl import URL

from ._core_base import DataType, request_director_v2
from .exceptions import DirectorServiceError
from .settings import DirectorV2Settings, get_plugin_settings

_log = logging.getLogger(__name__)


class _Params(BaseModel):
    user_id: PositiveInt | None = None
    project_id: str | None = None


async def list_dynamic_services(
    app: web.Application,
    user_id: PositiveInt | None = None,
    project_id: str | None = None,
) -> list[DynamicServiceGet]:
    params = _Params(user_id=user_id, project_id=project_id)
    params_dict = params.model_dump(exclude_none=True)
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
    return TypeAdapter(list[DynamicServiceGet]).validate_python(services)


# NOTE: ANE https://github.com/ITISFoundation/osparc-simcore/issues/3191
@log_decorator(logger=_log)
async def retrieve(
    app: web.Application, service_uuid: str, port_keys: list[ServicePortKey]
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


@log_decorator(logger=_log)
async def get_project_inactivity(
    app: web.Application,
    project_id: ProjectID,
    max_inactivity_seconds: NonNegativeInt,
) -> DataType:
    settings: DirectorV2Settings = get_plugin_settings(app)
    backend_url = (
        URL(settings.base_url) / f"dynamic_services/projects/{project_id}/inactivity"
    ).update_query(max_inactivity_seconds=max_inactivity_seconds)
    result = await request_director_v2(
        app, "GET", backend_url, expected_status=web.HTTPOk
    )
    assert isinstance(result, dict)  # nosec
    return result
