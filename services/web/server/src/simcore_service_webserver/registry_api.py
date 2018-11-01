""" API to the computational services registry

    TODO: move all apis to a submodule and rename as api
"""
# pylint: disable=C0103
import logging

from aiohttp import web
from simcore_director_sdk.rest import ApiException

from . import director_sdk

log = logging.getLogger(__file__)

registry_routes = web.RouteTableDef()


@registry_routes.get("/get_services")
async def get_services(request):
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
    print("HELLO!!!")
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
