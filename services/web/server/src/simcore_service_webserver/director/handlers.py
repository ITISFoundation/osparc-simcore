import logging

from aiohttp import web
from yarl import URL

from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_utils import extract_and_validate

from ..login.decorators import login_required
from .config import get_client_session, get_config

ANONYMOUS_USER = -1

log = logging.getLogger(__name__)


def _resolve_url(request: web.Request) -> URL:
    cfg = get_config(request.app)

    # director service API endpoint
    # TODO: service API endpoint could be deduced and checked upon setup (e.g. health check on startup)
    endpoint = URL.build(scheme='http', host=cfg['host'], port=cfg['port']).with_path(cfg["version"])

    # replace raw path, to keep the quotes and
    # strip webserver API version number from basepath
    # >>> URL('http://localhost:8091/v0/services/').raw_parts[2:]
    #    ('services', '')
    tail = "/".join(request.url.raw_parts[2:])

    url = (endpoint / tail).with_query(request.query)
    return url

# HANDLERS -------------------------------------------------------------------

@login_required
async def services_get(request: web.Request) -> web.Response:
    await extract_and_validate(request)

    url = _resolve_url(request)

    # forward to director API
    session = get_client_session(request.app)
    async with session.get(url, ssl=False) as resp:
        payload = await resp.json()
        return web.json_response(payload, status=resp.status)


@login_required
async def running_interactive_services_post(request: web.Request) -> web.Response:
    params, query, body = await extract_and_validate(request)

    assert not params
    assert query, "POST expected /running_interactive_services? ... "
    assert not body

    userid = request.get(RQT_USERID_KEY, ANONYMOUS_USER)
    url = _resolve_url(request)

    session = get_client_session(request.app)

    # get first if already running
    async with session.get(url, ssl=False) as resp:
        if resp.status == 200:
            # TODO: currently director API does not specify resp. 200
            payload = await resp.json()
        else:
            url = url.update_query( 
                user_id=userid,
                service_basepath='/x/'+ query['service_uuid'] # TODO: mountpoint should be setup!!
            )
            # otherwise, start new service
            async with session.post(url, ssl=False) as resp:
                payload = await resp.json()
    
    return web.json_response(payload, status=resp.status)


@login_required
async def running_interactive_services_get(request: web.Request) -> web.Response:
    params, query, body = await extract_and_validate(request)

    assert params, "GET expected /running_interactive_services/{service_uuid}"
    assert not query
    assert not body

    url = _resolve_url(request)

    # forward to director API
    session = get_client_session(request.app)
    async with session.get(url, ssl=False) as resp:
        payload = await resp.json()
        return web.json_response(payload, status=resp.status)



@login_required
async def running_interactive_services_delete(request: web.Request) -> web.Response:
    params, query, body = await extract_and_validate(request)

    assert params, "DELETE expected /running_interactive_services/{service_uuid}"
    assert not query
    assert not body

    url = _resolve_url(request)

    # forward to director API
    session = get_client_session(request.app)
    async with session.delete(url, ssl=False) as resp:
        payload = await resp.json()
        return web.json_response(payload, status=resp.status)
