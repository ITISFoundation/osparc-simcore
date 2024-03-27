""" Adds aiohttp middleware for tracing using zipkin server instrumentation.

"""

import logging
from collections.abc import Iterable

import aiozipkin as az
from aiohttp import web
from aiohttp.web import AbstractRoute
from aiozipkin.aiohttp_helpers import (
    APP_AIOZIPKIN_KEY,
    REQUEST_AIOZIPKIN_KEY,
    middleware_maker,
)
from yarl import URL

log = logging.getLogger(__name__)


def setup_tracing(
    app: web.Application,
    *,
    service_name: str,
    host: str,
    port: int,
    jaeger_base_url: URL | str,
    skip_routes: Iterable[AbstractRoute] | None = None,
) -> bool:
    """
    Sets up this service for a distributed tracing system
    using zipkin (https://zipkin.io/) and Jaeger (https://www.jaegertracing.io/)
    """
    zipkin_address = URL(f"{jaeger_base_url}") / "api/v2/spans"

    log.debug(
        "Setting up tracing for %s at %s:%d -> %s",
        service_name,
        host,
        port,
        zipkin_address,
    )

    endpoint = az.create_endpoint(service_name, ipv4=host, port=port)

    # TODO: move away from aiozipkin to OpenTelemetrySDK
    # https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/asgi/asgi.html
    # see issue [#2715](https://github.com/ITISFoundation/osparc-simcore/issues/2715)
    # creates / closes tracer
    async def _tracer_cleanup_context(app: web.Application):

        app[APP_AIOZIPKIN_KEY] = await az.create(
            f"{zipkin_address}", endpoint, sample_rate=1.0
        )

        yield

        if APP_AIOZIPKIN_KEY in app:
            await app[APP_AIOZIPKIN_KEY].close()

    app.cleanup_ctx.append(_tracer_cleanup_context)

    # adds middleware to tag spans (when used, tracer should be ready)
    m = middleware_maker(
        skip_routes=skip_routes,
        tracer_key=APP_AIOZIPKIN_KEY,
        request_key=REQUEST_AIOZIPKIN_KEY,
    )
    app.middlewares.append(m)

    # # WARNING: adds a middleware that should be the outermost since
    # # it expects stream responses while we allow data returns from a handler
    # az.setup(app, tracer, skip_routes=skip_routes)

    return True
