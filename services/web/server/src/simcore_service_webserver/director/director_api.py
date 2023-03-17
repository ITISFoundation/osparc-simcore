"""
    Facade to DIRECTOR service:
        - collection of functions to perform requests to the DIRECTOR services
"""

import logging
import urllib.parse
import warnings
from typing import Any, Optional

from aiohttp import ClientSession, web
from servicelib.aiohttp.client_session import get_client_session
from servicelib.utils import logged_gather
from yarl import URL

from . import director_exceptions
from .settings import DirectorSettings, get_plugin_settings

log = logging.getLogger(__name__)

warnings.warn("Director-v0 is deprecated, please use Director-v2", DeprecationWarning)


def _get_director_client(app: web.Application) -> tuple[ClientSession, URL]:
    settings: DirectorSettings = get_plugin_settings(app)
    api_endpoint = settings.base_url
    session = get_client_session(app)
    return session, api_endpoint


async def get_running_interactive_services(
    app: web.Application,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    session, api_endpoint = _get_director_client(app)

    params = {}
    if user_id:
        params["user_id"] = user_id
    if project_id:
        params["project_id"] = project_id

    url = (api_endpoint / "running_interactive_services").with_query(params)
    async with session.get(url) as resp:
        if resp.status < 400:
            payload = await resp.json()
            return payload["data"]
        return []


async def start_service(
    # pylint: disable=too-many-arguments
    app: web.Application,
    user_id: str,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
    request_dns: str,
    request_scheme: str,
    request_user_agent: str,
) -> Optional[dict]:
    session, api_endpoint = _get_director_client(app)

    params = {
        "user_id": user_id,
        "project_id": project_id,
        "service_key": service_key,
        "service_tag": service_version,
        "service_uuid": service_uuid,
        "service_basepath": f"/x/{service_uuid}",
    }

    headers = {
        "X-Dynamic-Sidecar-Request-DNS": request_dns,
        "X-Dynamic-Sidecar-Request-Scheme": request_scheme,
        "X-Dynamic-Sidecar-Request-User-Agent": request_user_agent,
    }

    url = (api_endpoint / "running_interactive_services").with_query(params)
    async with session.post(url, ssl=False, headers=headers) as resp:
        payload = await resp.json()
        return payload["data"]


async def stop_service(
    app: web.Application, service_uuid: str, save_state: Optional[bool] = True
) -> None:
    session, api_endpoint = _get_director_client(app)
    # stopping a service can take a lot of time
    # bumping the stop command timeout to 1 hour
    # this will allow to sava bigger datasets from the services

    settings: DirectorSettings = get_plugin_settings(app)

    url = api_endpoint / "running_interactive_services" / service_uuid
    async with session.delete(
        url,
        ssl=False,
        timeout=settings.DIRECTOR_STOP_SERVICE_TIMEOUT,
        params={"save_state": "true" if save_state else "false"},
    ) as resp:
        if resp.status == 404:
            raise director_exceptions.ServiceNotFoundError(service_uuid)
        if resp.status != 204:
            payload = await resp.json()
            raise director_exceptions.DirectorException(payload)


async def stop_services(
    app: web.Application,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    save_state: Optional[bool] = True,
) -> None:
    if not user_id and not project_id:
        raise ValueError("Expected either user or project")

    services = await get_running_interactive_services(
        app, user_id=user_id, project_id=project_id
    )

    stop_tasks = [stop_service(app, s["service_uuid"], save_state) for s in services]
    if stop_tasks:
        await logged_gather(*stop_tasks, reraise=True)


async def get_service_by_key_version(
    app: web.Application, service_key: str, service_version: str
) -> Optional[dict]:
    session, api_endpoint = _get_director_client(app)

    url = (
        api_endpoint
        / "services"
        / urllib.parse.quote(service_key, safe="")
        / service_version
    )
    async with session.get(url) as resp:
        if resp.status != 200:
            return
        payload = await resp.json()
        services = payload["data"]
        if not services:
            return
        return services[0]


async def get_services_extras(
    app: web.Application, service_key: str, service_version: str
) -> Optional[dict]:
    session, api_endpoint = _get_director_client(app)

    url = (
        api_endpoint
        / "service_extras"
        / urllib.parse.quote(service_key, safe="")
        / service_version
    )
    async with session.get(url) as resp:
        if resp.status != 200:
            log.warning("Status not 200 %s", resp)
            return
        payload = await resp.json()
        service_extras = payload["data"]
        if not service_extras:
            log.warning("Service extras is missing %s", resp)
            return
        return service_extras
