from enum import Enum

from aiohttp import web
from prometheus_client import Counter
from prometheus_client.registry import CollectorRegistry

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


MONITOR_SERVICE_STARTED = f"{__name__}.services_started"
MONITOR_SERVICE_STOPPED = f"{__name__}.services_stopped"

MONITOR_SERVICE_STARTED_LABELS: list[str] = [
    "service_key",
    "service_tag",
    "simcore_user_agent",
]

MONITOR_SERVICE_STOPPED_LABELS: list[str] = [
    "service_key",
    "service_tag",
    "result",
    "simcore_user_agent",
]


def add_instrumentation(
    app: web.Application, reg: CollectorRegistry, app_name: str
) -> None:
    app[MONITOR_SERVICE_STARTED] = Counter(
        name="services_started_total",
        documentation="Counts the services started",
        labelnames=MONITOR_SERVICE_STARTED_LABELS,
        namespace="simcore",
        subsystem=app_name,
        registry=reg,
    )

    app[MONITOR_SERVICE_STOPPED] = Counter(
        name="services_stopped_total",
        documentation="Counts the services stopped",
        labelnames=MONITOR_SERVICE_STOPPED_LABELS,
        namespace="simcore",
        subsystem=app_name,
        registry=reg,
    )


class ServiceResult(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


def service_started(
    # pylint: disable=too-many-arguments
    app: web.Application,
    service_key: str,
    service_tag: str,
    simcore_user_agent: str,
) -> None:
    app[MONITOR_SERVICE_STARTED].labels(
        service_key=service_key,
        service_tag=service_tag,
        simcore_user_agent=simcore_user_agent,
    ).inc()


def service_stopped(
    # pylint: disable=too-many-arguments
    app: web.Application,
    service_key: str,
    service_tag: str,
    simcore_user_agent: str,
    result: ServiceResult | str,
) -> None:
    app[MONITOR_SERVICE_STOPPED].labels(
        service_key=service_key,
        service_tag=service_tag,
        simcore_user_agent=simcore_user_agent,
        result=result.name if isinstance(result, ServiceResult) else result,
    ).inc()
