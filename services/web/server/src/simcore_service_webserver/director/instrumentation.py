from aiohttp import web
from prometheus_client import Counter
from prometheus_client.registry import CollectorRegistry


kSERVICE_STARTED = f"{__name__}.director_services_started"
kSERVICE_STOPPED = f"{__name__}.director_services_stopped"


def add_instrumentation(app: web.Application, reg: CollectorRegistry) -> None:

    app[kSERVICE_STARTED] = Counter(
        name="services_started_total",
        documentation="Counts the services started",
        labelnames=[
            "user_id",
            "project_id",
            "service_key",
            "service_tag",
            "service_uuid",
            "http_status",
        ],
        subsystem="director",
        namespace="webserver",
        registry=reg,
    )

    app[kSERVICE_STOPPED] = Counter(
        name="services_stopped_total",
        documentation="Counts the services stopped",
        labelnames=["service_uuid", "http_status",],
        subsystem="director",
        namespace="webserver",
        registry=reg,
    )
