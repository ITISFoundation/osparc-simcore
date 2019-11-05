"""

    Adds aiohttp middleware for tracing using zipkin server instrumentation.


"""

import asyncio
import logging
from typing import Dict

import aiozipkin as az
import trafaret as T
from aiohttp import web

log = logging.getLogger(__name__)

def setup_tracing(app: web.Application, app_name: str, host: str, port: str, config: Dict) -> bool:
    zipkin_address = f"{config['zipkin_endpoint']}/api/v2/spans"
    endpoint = az.create_endpoint(app_name, ipv4=host, port=port)
    loop = asyncio.get_event_loop()
    tracer = loop.run_until_complete(az.create(zipkin_address, endpoint, sample_rate=1.0))
    az.setup(app, tracer)
    return True

schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.Int),
    T.Key('zipkin_endpoint', default="http://jaeger:9411"): T.String()
    }
)
