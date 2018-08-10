""" API to the computational services registry

    TODO: move all apis to a submodule and rename as api
"""
# pylint: disable=C0103
import logging

from aiohttp import web
import async_timeout

from . import director_proxy

_LOGGER = logging.getLogger(__file__)

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
    - service registry
    produces:
    - application/json
    responses:
        "200":
            description: successful operation. Return "pong" text
        "405":
            description: invalid HTTP Method
    """
    _LOGGER.debug(request)

    repo_list = director_proxy.retrieve_computational_services()

    return web.json_response(repo_list)
