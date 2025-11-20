# pylint: disable=protected-access

import asyncio
import logging
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Final

from fastapi import FastAPI, Request, Response, status
from fastapi_lifespan_manager import State
from prometheus_client import CollectorRegistry
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match, Route
from starlette.types import ASGIApp

from ..common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from ..prometheus_metrics import (
    PrometheusMetrics,
    get_prometheus_metrics,
    record_asyncio_event_looop_metrics,
    record_request_metrics,
    record_response_metrics,
)

_logger = logging.getLogger(__name__)
_PROMETHEUS_METRICS = "prometheus_metrics"


def _get_route_details(scope):
    """
    Function to retrieve Starlette route from scope.

    TODO: there is currently no way to retrieve http.route from
    a starlette application from scope.
    See: https://github.com/encode/starlette/pull/804

    Args:
        scope: A Starlette scope
    Returns:
        A string containing the route or None
    """
    app = scope["app"]
    route = None

    for starlette_route in app.routes:
        match, _ = (
            Route.matches(starlette_route, scope)
            if isinstance(starlette_route, Route)
            else starlette_route.matches(scope)
        )
        if match == Match.FULL:
            try:
                route = starlette_route.path
            except AttributeError:
                # routes added via host routing won't have a path attribute
                route = scope.get("path")
            break
        if match == Match.PARTIAL:
            route = starlette_route.path
    return route


class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics: PrometheusMetrics):
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        canonical_endpoint = _get_route_details(request.scope)
        canonical_endpoint = canonical_endpoint or request.url.path

        user_agent = request.headers.get(
            X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
        )

        start_time = perf_counter()
        try:
            with record_request_metrics(
                metrics=self.metrics,
                method=request.method,
                endpoint=canonical_endpoint,
                user_agent=user_agent,
            ):
                response = await call_next(request)
                status_code = response.status_code

        except Exception:  # pylint: disable=broad-except
            # NOTE: The prometheus metrics middleware should be "outside" exception handling
            # middleware. See https://fastapi.tiangolo.com/advanced/middleware/#adding-asgi-middlewares
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            raise
        finally:
            reponse_latency_seconds = perf_counter() - start_time
            record_response_metrics(
                metrics=self.metrics,
                method=request.method,
                endpoint=canonical_endpoint,
                user_agent=user_agent,
                http_status=status_code,
                response_latency_seconds=reponse_latency_seconds,
            )

        return response


def initialize_prometheus_instrumentation(app: FastAPI) -> None:
    metrics = get_prometheus_metrics()
    app.state.prometheus_metrics = metrics
    app.add_middleware(PrometheusMiddleware, metrics=metrics)


def _startup(app: FastAPI) -> None:
    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(request: Request) -> Response:
        prometheus_metrics = request.app.state.prometheus_metrics
        assert isinstance(prometheus_metrics, PrometheusMetrics)  # nosec
        await record_asyncio_event_looop_metrics(prometheus_metrics)

        content = await asyncio.get_event_loop().run_in_executor(
            None, generate_latest, prometheus_metrics.registry
        )

        return Response(content=content, headers={"Content-Type": CONTENT_TYPE_LATEST})


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
