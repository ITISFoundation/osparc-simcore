import logging

from aiohttp import web
from yarl import URL

from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_utils import extract_and_validate

from ..login.decorators import login_required
from .config import get_client_session, get_config

log = logging.getLogger(__name__)


async def _request_storage(request: web.Request, method: str):
    await extract_and_validate(request)
    # replace raw path, to keep the quotes
    url_path = request.rel_url.raw_path.replace("director/", "")

    cfg = get_config(request.app)
    urlbase = URL.build(scheme='http', host=cfg['host'], port=cfg['port'])

    userid = request[RQT_USERID_KEY]
    url = urlbase.with_path(url_path).with_query(user_id=userid)

    session = get_client_session(request.app)
    async with session.request(method.upper(), url, ssl=False) as resp:
        payload = await resp.json()
        return payload

@login_required
async def running_interactive_services_post(request: web.Request):
    payload = await _request_storage(request, 'POST')
    return payload
    # log.debug("client starts dynamic service %s", request)
    # try:
    #     service_key = data["serviceKey"]
    #     service_version = "latest"
    #     # if "serviceVersion" in data:
    #     #     service_version = data["serviceVersion"]
    #     node_id = data["nodeId"]
    #     result = await interactive_services_manager.start_service(sid, service_key, node_id, service_version)
    #     await sio.emit("startDynamic", data=result, room=sid)
    # except IOError:
    #     log.exception("Error emitting results")
    # except Exception:
    #     log.exception("Error while starting service")

@login_required
async def running_interactive_services_get(request: web.Request):
    payload = await _request_storage(request, 'GET')
    return payload

@login_required
async def running_interactive_services_delete(request: web.Request):
    payload = await _request_storage(request, 'DELETE')
    return payload

    # log.debug("client %s stops dynamic service %s", sid, data)
    # try:
    #     node_id = data["nodeId"]
    #     await interactive_services_manager.stop_service(sid, node_id)
    # except Exception:
    #     log.exception("Error while stopping service")

@login_required
async def services_get(request):
    payload = await _request_storage(request, 'GET')
    return payload
