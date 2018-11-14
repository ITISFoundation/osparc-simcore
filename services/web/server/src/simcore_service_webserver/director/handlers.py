import logging
from aiohttp import web
from ..login.decorators import login_required
from . import director_sdk

log = logging.getLogger(__name__)

@login_required
async def running_interactive_services_post(request: web.Request):
    pass

@login_required
async def running_interactive_services_get(request: web.Request):
    pass

@login_required
async def running_interactive_services_delete(request: web.Request):
    pass

@login_required
async def services_get(request):
    log.debug(request)
    try:
        director = director_sdk.get_director()
        services = await director.services_get()
        return web.json_response(services.to_dict())
    except ApiException as exc:
        log.exception("Api Error while accessing director")
        return web.json_response(exc.reason, status=exc.status)
    except Exception:
        log.exception("Error while retrieving computational services")
        raise
