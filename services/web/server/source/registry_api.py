"""
    Uses socketio and aiohtttp framework
"""
# pylint: disable=C0103

from aiohttp import web

registry_routes = web.RouteTableDef()

@registry_routes.get('/services')
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
    return web.Response(text="This will be a list of comp. services")
