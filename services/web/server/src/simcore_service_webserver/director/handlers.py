import logging

from aiohttp import web
from yarl import URL

from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_utils import extract_and_validate

from ..login.decorators import login_required
from .config import get_client_session, get_config

log = logging.getLogger(__name__)

async def _request_storage(request: web.Request, method: str = None) -> web.Response:
    await extract_and_validate(request)
    if method is None:
        method = request.method
    # replace raw path, to keep the quotes
    url_path = request.rel_url.raw_path.replace("director/", "")

    cfg = get_config(request.app)
    urlbase = URL.build(scheme='http', host=cfg['host'], port=cfg['port'])

    userid = request[RQT_USERID_KEY]
    url = urlbase.with_path(url_path).with_query(user_id=userid)

    session = get_client_session(request.app)
    async with session.request(str(method).upper(), url, ssl=False) as resp:
        payload = await resp.json()
        return payload

@login_required
async def running_interactive_services_post(request: web.Request) -> web.Response:
    payload = await _request_storage(request)
    if payload.status == 200:
        # TODO: add the service to the list of service for this user
        pass
    return payload

@login_required
async def running_interactive_services_get(request: web.Request) -> web.Response:
    payload = await _request_storage(request)
    return payload

@login_required
async def running_interactive_services_delete(request: web.Request) -> web.Response:
    payload = await _request_storage(request)
    if payload.status == 204:
        #TODO: remove the service from the list of services for this user
        pass
    return payload

@login_required
async def services_get(request: web.Request) -> web.Response:
    payload = await _request_storage(request)
    return payload
