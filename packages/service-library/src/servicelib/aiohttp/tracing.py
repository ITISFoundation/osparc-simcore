""" Adds aiohttp middleware for tracing using zipkin server instrumentation.

"""
import logging
from typing import Union

import aiozipkin as az
from aiohttp import web
from yarl import URL

log = logging.getLogger(__name__)


DEFAULT_JAEGER_BASE_URL = "http://jaeger:9411"


def setup_tracing(
    app: web.Application,
    *,
    service_name: str,
    host: str,
    port: int,
    jaeger_base_url: Union[URL, str],
) -> bool:
    """
    Sets up this service for a distributed tracing system
    using zipkin (https://zipkin.io/) and Jaeger (https://www.jaegertracing.io/)
    """
    zipkin_address = URL(f"{jaeger_base_url}") / "api/v2/spans"

    log.debug(
        "Settings up tracing for %s(%s:%d) -> %s",
        service_name,
        host,
        port,
        zipkin_address,
    )

    async def _on_startup(app: web.Application):
        endpoint = az.create_endpoint(service_name, ipv4=host, port=port)
        tracer = await az.create(f"{zipkin_address}", endpoint, sample_rate=1.0)
        az.setup(app, tracer)

    app.on_startup.append(_on_startup)
    return True
