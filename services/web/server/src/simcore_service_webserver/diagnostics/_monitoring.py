""" Enables monitoring of some quantities needed for diagnostics

"""
import logging
import time

from aiohttp import web
from servicelib.aiohttp import monitor_services
from servicelib.aiohttp.monitoring import get_collector_registry
from servicelib.aiohttp.monitoring import setup_monitoring as service_lib_setup

from .. import _meta
from ._healthcheck import HEALTH_LATENCY_PROBE, DelayWindowProbe, is_sensing_enabled

_logger = logging.getLogger(__name__)

#
# CAUTION CAUTION CAUTION NOTE:
# Be very careful with metrics. pay attention to metrics cardinatity.
# Each time series takes about 3kb of overhead in Prometheus
#
# CAUTION: every unique combination of key-value label pairs represents a new time series
#
# If a metrics is not needed, don't add it!! It will collapse the application AND prometheus
#
# references:
# https://prometheus.io/docs/practices/naming/
# https://www.robustperception.io/cardinality-is-key
# https://www.robustperception.io/why-does-prometheus-use-so-much-ram
# https://promcon.io/2019-munich/slides/containing-your-cardinality.pdf
# https://grafana.com/docs/grafana-cloud/how-do-i/control-prometheus-metrics-usage/usage-analysis-explore/
#


kSTART_TIME = f"{__name__}.start_time"


async def enter_middleware_cb(request: web.Request):
    request[kSTART_TIME] = time.time()


async def exit_middleware_cb(request: web.Request, _response: web.StreamResponse):
    resp_time_secs: float = time.time() - request[kSTART_TIME]
    if not str(request.path).startswith("/socket.io") and is_sensing_enabled(
        request.app
    ):
        request.app[HEALTH_LATENCY_PROBE].observe(resp_time_secs)


def setup_monitoring(app: web.Application):
    service_lib_setup(
        app,
        _meta.APP_NAME,
        enter_middleware_cb=enter_middleware_cb,
        exit_middleware_cb=exit_middleware_cb,
        version=f"{_meta.VERSION}",
    )

    monitor_services.add_instrumentation(
        app, get_collector_registry(app), _meta.APP_NAME
    )

    # on-the fly stats
    app[HEALTH_LATENCY_PROBE] = DelayWindowProbe()

    return True
