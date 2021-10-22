""" Adds aiohttp middleware for tracing using zipkin server instrumentation.

"""
import asyncio
import logging
from typing import Iterable, Optional, Union

import aiozipkin as az
from aiohttp import web
from aiohttp.web import AbstractRoute
from aiozipkin.tracer import Tracer
from yarl import URL

log = logging.getLogger(__name__)


def setup_tracing(
    app: web.Application,
    *,
    service_name: str,
    host: str,
    port: int,
    jaeger_base_url: Union[URL, str],
    skip_routes: Optional[Iterable[AbstractRoute]] = None,
) -> bool:
    """
    Sets up this service for a distributed tracing system
    using zipkin (https://zipkin.io/) and Jaeger (https://www.jaegertracing.io/)
    """
    zipkin_address = URL(f"{jaeger_base_url}") / "api/v2/spans"

    log.debug(
        "Settings up tracing for %s at %s:%d -> %s",
        service_name,
        host,
        port,
        zipkin_address,
    )

    endpoint = az.create_endpoint(service_name, ipv4=host, port=port)

    tracer: Tracer = asyncio.get_event_loop().run_until_complete(
        az.create(f"{zipkin_address}", endpoint, sample_rate=1.0)
    )

    # WARNING: adds a middleware that should be the outermost since
    # it expects stream responses while we allow data returns from a handler
    az.setup(app, tracer, skip_routes=skip_routes)

    return True
