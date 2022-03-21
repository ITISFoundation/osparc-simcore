""" Basic diagnostic handles to the rest API for operations


"""
import logging

from aiohttp import web
from servicelib.aiohttp.rest_utils import extract_and_validate

from ._meta import __version__, api_version_prefix
from .application_settings import APP_SETTINGS_KEY
from .rest_healthcheck import HealthCheckFailed, HeathCheck

log = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get(f"/{api_version_prefix}/health", name="check_health")
async def check_health(request: web.Request):

    healthcheck: HeathCheck = request.app[HeathCheck.__name__]

    if timeout := request.app[APP_SETTINGS_KEY].SC_HEALTHCHECK_TIMEOUT:
        # Let's cancel check if goes 10% over healtcheck timeout
        timeout *= 1.1
        log.debug("Healthcheck %s", f"{timeout=}")

    try:
        health_report = await healthcheck.run(request.app, timeout=timeout)
    except HealthCheckFailed as err:
        log.warning("%s", err)
        raise web.HTTPServiceUnavailable(reason="unhealthy")

    except Exception as err:
        log.exception(err)
        raise web.HTTPServiceUnavailable(reason="unhealthy")

    return web.json_response(data={"data": health_report})


@routes.get(f"/{api_version_prefix}/", name="check_running")
async def check_running(_request: web.Request):
    #
    # - This entry point is used as a fast way
    #   to check that the service is still running
    # - Do not do add any expensive computatio here
    # - Healthcheck has been moved to diagnostics module
    #
    health_report = {
        "name": __name__.split(".")[0],
        "version": f"{__version__}",
        "status": "SERVICE_RUNNING",
        "api_version": f"{__version__}",
    }
    return web.json_response(data={"data": health_report})


@routes.get(f"/{api_version_prefix}/config", name="get_config")
async def get_config(request: web.Request):
    """
    This entrypoint aims to provide an extra configuration mechanism for
    the front-end app.

    Some of the server configuration can be forwarded to the front-end here

    Example use case: the front-end app is served to the client. Then the user wants to
    register but the server has been setup to require an invitation. This option is setup
    at runtime and the front-end can only get it upon request to /config
    """
    await extract_and_validate(request)

    return web.json_response(data={"data": request.app[APP_SETTINGS_KEY].public_dict()})
