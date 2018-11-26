import logging
from typing import Optional

from aiohttp import web
from yarl import URL

from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_utils import extract_and_validate

from ..login.decorators import login_required
from .config import get_client_session, get_config

log = logging.getLogger(__name__)


async def _request_director(request: web.Request, method: Optional[str] = None) -> web.Response:
    params, query, body = await extract_and_validate(request)
    method = method or request.method

    cfg = get_config(request.app)

    # director service API endpoint
    # TODO: service API endpoint could be deduced and checked upon setup (e.g. health check on startup)
    endpoint = URL.build(scheme='http', host=cfg['host'], port=cfg['port']).with_path(cfg["version"])

    # replace raw path, to keep the quotes and
    # strip webserver API version number from basepath
    # >>> URL('http://localhost:8091/v0/services/').raw_parts[2:]
    #    ('services', '')
    tail = "/".join(request.url.raw_parts[2:])

    # add the user id
    userid = request[RQT_USERID_KEY]
    query["user_id"] = userid
    url = (endpoint / tail).with_query(query)

    # forward the call
    session = get_client_session(request.app)
    async with session.request(str(method).upper(), url, ssl=False, params=params, data=body) as resp:
        payload = await resp.json()
        return payload

@login_required
async def running_interactive_services_post(request: web.Request) -> web.Response:
    payload = await _request_director(request)
    # if payload.status == 200:
    #     # TODO: add the service to the list of service for this user
    #     pass
    return payload

@login_required
async def running_interactive_services_get(request: web.Request) -> web.Response:
    payload = await _request_director(request)
    return payload

@login_required
async def running_interactive_services_delete(request: web.Request) -> web.Response:
    payload = await _request_director(request)
    # if payload.status == 204:
    #     #TODO: remove the service from the list of services for this user
    #     pass
    return payload

@login_required
async def services_get(request: web.Request) -> web.Response:
    payload = await _request_director(request)
    return payload
