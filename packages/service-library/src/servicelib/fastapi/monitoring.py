# pylint: disable=protected-access

from collections.abc import AsyncIterator
from typing import Final

import prometheus_client
from fastapi import FastAPI, Request, Response
from fastapi_lifespan_manager import State
from prometheus_client import CollectorRegistry
from servicelib.prometheus_metrics import (
    PrometheusMetrics,
    record_request_metrics,
    record_response_metrics,
    setup_prometheus_metrics,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from ..common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)

kPROMETHEUS_METRICS = "prometheus_metrics"


class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics: PrometheusMetrics):
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        canonical_endpoint = request.url.path
        user_agent = request.headers.get(
            X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
        )

        try:
            with record_request_metrics(
                metrics=self.metrics,
                method=request.method,
                endpoint=canonical_endpoint,
                user_agent=user_agent,
            ):
                response = await call_next(request)
        finally:
            record_response_metrics(
                metrics=self.metrics,
                method=request.method,
                endpoint=canonical_endpoint,
                user_agent=user_agent,
                http_status=response.status_code,
            )

        return response


def initialize_prometheus_instrumentation(app: FastAPI) -> None:
    # NOTE: this cannot be ran once the application is started

    # NOTE: use that registry to prevent having a global one
    metrics = setup_prometheus_metrics()
    app.state.prometheus_metrics = metrics
    app.add_middleware(PrometheusMiddleware, metrics=metrics)


def _startup(app: FastAPI) -> None:
    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(request: Request) -> Response:
        """
        Exposes the Prometheus metrics endpoint.
        """
        prometheus_metrics = request.app.state.prometheus_metrics
        assert isinstance(prometheus_metrics, PrometheusMetrics)  # nosec
        return Response(
            content=prometheus_client.generate_latest(prometheus_metrics.registry),
            media_type="text/plain",
        )


def _shutdown(app: FastAPI) -> None:
    prometheus_metrics = app.state.prometheus_metrics
    assert isinstance(prometheus_metrics, PrometheusMetrics)  # nosec
    registry = prometheus_metrics.registry
    for collector in list(registry._collector_to_names.keys()):  # noqa: SLF001
        registry.unregister(collector)


def setup_prometheus_instrumentation(app: FastAPI) -> CollectorRegistry:
    initialize_prometheus_instrumentation(app)

    async def _on_startup() -> None:
        _startup(app)

    def _on_shutdown() -> None:
        _shutdown(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    prometheus_metrics = app.state.prometheus_metrics
    assert isinstance(prometheus_metrics, PrometheusMetrics)  # nosec

    return prometheus_metrics.registry


_PROMETHEUS_INSTRUMENTATION_ENABLED: Final[str] = "prometheus_instrumentation_enabled"


def create_prometheus_instrumentationmain_input_state(*, enabled: bool) -> State:
    return {_PROMETHEUS_INSTRUMENTATION_ENABLED: enabled}


async def prometheus_instrumentation_lifespan(
    app: FastAPI, state: State
) -> AsyncIterator[State]:
    # NOTE: requires ``initialize_prometheus_instrumentation`` to be called before the
    # lifespan of the applicaiton runs, usually rigth after the ``FastAPI`` instance is created

    instrumentaiton_enabled = state.get(_PROMETHEUS_INSTRUMENTATION_ENABLED, False)
    if instrumentaiton_enabled:

        _startup(app)
    yield {}
    if instrumentaiton_enabled:
        _shutdown(app)
