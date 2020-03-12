 # pylint: disable=too-many-arguments

import logging
import urllib
from typing import Dict, List, Optional

from aiohttp import web
from yarl import URL

from servicelib.utils import logged_gather

from . import director_exceptions
from .config import get_client_session, get_config

log = logging.getLogger(__name__)


def _get_director_client(app: web.Application) -> URL:
    cfg = get_config(app)

    # director service API endpoint
    # TODO: service API endpoint could be deduced and checked upon setup (e.g. health check on startup)
    # Use director.
    # TODO: this is also in app[APP_DIRECTOR_API_KEY] upon startup
    api_endpoint = URL.build(
        scheme="http", host=cfg["host"], port=cfg["port"]
    ).with_path(cfg["version"])

    session = get_client_session(app)
    return session, api_endpoint


async def get_running_interactive_services(
    app: web.Application,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> List[Dict]:
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
    app: web.Application,
    user_id: str,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
) -> Optional[Dict]:
    session, api_endpoint = _get_director_client(app)

    params = {
        "user_id": user_id,
        "project_id": project_id,
        "service_key": service_key,
        "service_tag": service_version,
        "service_uuid": service_uuid,
        "service_basepath": f"/x/{service_uuid}",
    }

    url = (api_endpoint / "running_interactive_services").with_query(params)
    async with session.post(url, ssl=False) as resp:
        payload = await resp.json()
        return payload["data"]


async def stop_service(app: web.Application, service_uuid: str) -> None:
    session, api_endpoint = _get_director_client(app)

    url = api_endpoint / "running_interactive_services" / service_uuid
    async with session.delete(url, ssl=False) as resp:
        if resp.status == 404:
            raise director_exceptions.ServiceNotFoundError(service_uuid)
        if resp.status != 204:
            payload = await resp.json()
            raise director_exceptions.DirectorException(payload)


async def stop_services(
    app: web.Application,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> None:
    if not user_id and not project_id:
        raise ValueError("Expected either user or project")

    services = await get_running_interactive_services(
        app, user_id=user_id, project_id=project_id
    )
    stop_tasks = [stop_service(app, service_uuid) for service_uuid in services]
    await logged_gather(*stop_tasks, reraise=False)


async def get_service_by_key_version(
    app: web.Application, service_key: str, service_version: str
) -> Optional[Dict]:
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
