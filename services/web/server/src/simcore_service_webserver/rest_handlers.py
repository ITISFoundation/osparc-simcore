""" Basic healthckeck and configuration handles to the rest API


"""
import logging

from aiohttp import web

from ._meta import api_version_prefix
from .application_settings import APP_SETTINGS_KEY
from .redis import get_redis_scheduled_maintenance_client
from .rest_healthcheck import HealthCheck, HealthCheckFailed

log = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get(f"/{api_version_prefix}/health", name="healthcheck_liveness_probe")
async def healthcheck_liveness_probe(request: web.Request):
    """Liveness probe: "Check if the container is alive"

    This is checked by the containers orchestrator (docker swarm). When the service
    is unhealthy, it will restart it so it can recover a working state.

    SEE doc in rest_healthcheck.py
    """
    healthcheck: HealthCheck = request.app[HealthCheck.__name__]

    try:
        # if slots append get too delayed, just timeout
        health_report = await healthcheck.run(request.app)
    except HealthCheckFailed as err:
        log.warning("%s", err)
        raise web.HTTPServiceUnavailable(reason="unhealthy")

    return web.json_response(data={"data": health_report})


@routes.get(f"/{api_version_prefix}/", name="healthcheck_readiness_probe")
async def healthcheck_readiness_probe(request: web.Request):
    """Readiness probe: "Check if the container is ready to receive traffic"

    When the target service is unhealthy, no traffic should be sent to it. Service discovery
    services and load balancers (e.g. traefik) typically cut traffic from targets
    in one way or another.

    SEE doc in rest_healthcheck.py
    """

    healthcheck: HealthCheck = request.app[HealthCheck.__name__]
    health_report = healthcheck.get_app_info(request.app)
    # NOTE: do NOT run healthcheck here, just return info fast.
    health_report["status"] = "SERVICE_RUNNING"

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
    return web.json_response(data={"data": request.app[APP_SETTINGS_KEY].public_dict()})


@routes.get(f"/{api_version_prefix}/scheduled_maintenance", name="get_scheduled_maintenance")
async def get_scheduled_maintenance(request: web.Request):
    """Check scheduled_maintenance table in redis"""

    redis_client = get_redis_scheduled_maintenance_client(request.app)
    hash_key = "maintenance"
    maintenance = await redis_client.get(hash_key)
    log.warning("%s", maintenance)
    if maintenance is not None:
        maintenance_data = {
            "start": maintenance.start,
            "end": maintenance.end,
            "reason": maintenance.reason,
        }
        return web.json_response(data={"data": maintenance_data})
    return web.json_response(status=204)
