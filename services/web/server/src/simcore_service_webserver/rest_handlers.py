""" Basic healthckeck and configuration handles to the rest API


"""
import logging
from typing import Any

from aiohttp import web

from ._constants import APP_PUBLIC_CONFIG_PER_PRODUCT
from ._meta import API_VTAG
from .application_settings import APP_SETTINGS_KEY
from .products import get_product_name
from .redis import get_redis_scheduled_maintenance_client
from .rest_healthcheck import HealthCheck, HealthCheckFailed
from .utils_aiohttp import envelope_json_response

log = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/health", name="healthcheck_liveness_probe")
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


@routes.get(f"/{API_VTAG}/", name="healthcheck_readiness_probe")
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
    return envelope_json_response(health_report)


@routes.get(f"/{API_VTAG}/config", name="get_config")
async def get_config(request: web.Request):
    """
    This entrypoint aims to provide an extra configuration mechanism for
    the front-end app.

    Some of the server configuration can be forwarded to the front-end here

    Example use case: the front-end app is served to the client. Then the user wants to
    register but the server has been setup to require an invitation. This option is setup
    at runtime and the front-end can only get it upon request to /config
    """
    app_public_config: dict[str, Any] = request.app[APP_SETTINGS_KEY].public_dict()

    product_name = get_product_name(request=request)
    product_public_config = request.app.get(APP_PUBLIC_CONFIG_PER_PRODUCT, {}).get(
        product_name, {}
    )

    return envelope_json_response(app_public_config | product_public_config)


@routes.get(f"/{API_VTAG}/scheduled_maintenance", name="get_scheduled_maintenance")
async def get_scheduled_maintenance(request: web.Request):
    """Check scheduled_maintenance table in redis"""

    redis_client = get_redis_scheduled_maintenance_client(request.app)
    hash_key = "maintenance"
    # {"start": "2023-01-17T14:45:00.000Z", "end": "2023-01-17T23:00:00.000Z", "reason": "Release 1.0.4"}
    if maintenance_str := await redis_client.get(hash_key):
        return web.json_response(data={"data": maintenance_str})

    return web.json_response(status=204)
