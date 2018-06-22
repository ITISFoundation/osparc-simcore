"""
    Uses socketio and aiohtttp framework
"""
# pylint: disable=C0103

from aiohttp import web
import async_timeout

import director_proxy

registry_routes = web.RouteTableDef()

async def async_request(method, session, url, data=None, timeout=10):
    async with async_timeout.timeout(timeout):
        if method == "GET":
            async with session.get(url) as response:
                return await response.json()
        elif method == "POST":
            async with session.post(url, json=data) as response:
                return await response.json()



@registry_routes.get('/repositories')
async def services(request):
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
    _a = request

    repo_list = director_proxy.retrieve_repositories()

    return web.json_response(repo_list)
