""" API to the computational services registry

    TODO: move all apis to a submodule and rename as api
"""
# pylint: disable=C0103
import logging

import async_timeout
from aiohttp import web
from simcore_director_sdk.rest import ApiException

from . import director_sdk

log = logging.getLogger(__file__)

registry_routes = web.RouteTableDef()

async def async_request(method, session, url, data=None, timeout=10):
    async with async_timeout.timeout(timeout):
        if method == "GET":
            async with session.get(url) as response:
                return await response.json()
        elif method == "POST":
            async with session.post(url, json=data) as response:
                return await response.json()



@registry_routes.get("/get_computational_services")
async def get_computational_services(request):
    """
    ---
    description: This end-point returns a list of computational services.
    tags:
    - services management
    produces:
    - application/json
    responses:
        "200":
            description: successful operation. Return "pong" text
        "405":
            description: invalid HTTP Method
    """
    log.debug(request)

    try:
        director = director_sdk.get_director()
        services = await director.services_get(service_type="computational")
        return web.json_response(services.to_dict())
    except ApiException as exc:
        log.exception("Api Error while accessing director")
        return web.json_response(exc.reason, status=exc.status)
    except Exception:
        log.exception("Error while retrieving computational services")
        raise
