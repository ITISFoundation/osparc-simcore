import logging

from aiohttp import web
from yarl import URL

from .config import get_client_session, get_config
from .registry import get_registry


log = logging.getLogger(__name__)


def _get_director_client(app: web.Application) -> URL:
    cfg = get_config(app)

    # director service API endpoint
    # TODO: service API endpoint could be deduced and checked upon setup (e.g. health check on startup)
    api_endpoint = URL.build(
        scheme='http',
        host=cfg['host'],
        port=cfg['port']).with_path(cfg["version"])

    session = get_client_session(app)
    return session, api_endpoint


#@fire_and_forget
async def stop_service(app: web.Application, service_uuid:str):
    registry = get_registry(app)
    session, api_endpoint = _get_director_client(app)

    url = (api_endpoint / service_uuid)
    async with session.delete(url, ssl=False) as resp:
        payload = await resp.json()
        if resp.status < 400 or resp.status == 404:
            registry.as_stopped(service_uuid)
        return payload, resp.status
