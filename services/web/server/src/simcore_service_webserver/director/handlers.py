import logging

from aiohttp import web
from yarl import URL

from servicelib.observer import observe
from servicelib.rest_utils import extract_and_validate

from ..login.decorators import login_required
from ..security_api import check_permission
from . import director_api
from .config import get_client_session, get_config

ANONYMOUS_USER_ID = -1

log = logging.getLogger(__name__)


def _forward_url(app: web.Application, url: URL) -> URL:
    # replace raw path, to keep the quotes and
    # strip webserver API version number from basepath
    # >>> URL('http://localhost:8091/v0/services/').raw_parts[2:]
    #    ('services', '')
    cfg = get_config(app)

    # director service API endpoint
    # TODO: service API endpoint could be deduced and checked upon setup (e.g. health check on startup)
    endpoint = URL.build(
        scheme='http',
        host=cfg['host'],
        port=cfg['port']).with_path(cfg["version"])
    tail = "/".join(url.raw_parts[2:])

    url = (endpoint / tail)
    return url

def _resolve_url(request: web.Request) -> URL:
    return _forward_url(request.app, request.url)

# HANDLERS -------------------------------------------------------------------

@login_required
async def services_get(request: web.Request) -> web.Response:
    await check_permission(request, "services.catalog.*")
    await extract_and_validate(request)

    url = _resolve_url(request)
    url = url.with_query(request.query)

    # forward to director API
    session = get_client_session(request.app)
    async with session.get(url, ssl=False) as resp:
        payload = await resp.json()
        return web.json_response(payload, status=resp.status)

@observe(event="SIGNAL_USER_LOGOUT")
async def delete_all_services_for_user_signal_handler(user_id: str, app: web.Application) -> None:
    await director_api.stop_services(app, user_id=user_id)
