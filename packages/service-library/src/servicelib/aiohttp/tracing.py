""" Adds aiohttp middleware for tracing using zipkin server instrumentation.

"""
import asyncio
import logging
import time
from contextlib import contextmanager
from typing import Iterable, Optional, Union

import aiozipkin as az
from aiohttp import web
from aiohttp.web import AbstractRoute
from aiozipkin.tracer import Tracer
from yarl import URL

log = logging.getLogger(__name__)


DEFAULT_JAEGER_BASE_URL = "http://jaeger:9411"


@contextmanager
def _timeit(what: str, minimum_expected_secs: int = 2):
    """Small helper to time and log"""
    try:
        _tic = time.time()

        yield

        _elapsed = time.time() - _tic
        msg = f"{what}: elapsed {_elapsed:3.2f} sec"
        if _elapsed > minimum_expected_secs:
            log.debug(msg)
        else:
            log.warning(msg)
    except:
        log.warning("Failed %s", what)
        raise


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

    with _timeit("Created aiozipkin.tracer.Tracer"):
        tracer: Tracer = asyncio.get_event_loop().run_until_complete(
            az.create(f"{zipkin_address}", endpoint, sample_rate=1.0)
        )

    # WARNING: adds a middleware that should be the outermost since
    # it expects stream responses while we allow data returns from a handler
    az.setup(app, tracer, skip_routes=skip_routes)

    return True
