import prometheus_client
from fastapi import FastAPI, Request, Response
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


def setup_monitoring(
    app: FastAPI,
) -> None:
    metrics = setup_prometheus_metrics()
    app.state.prometheus_metrics = metrics
    app.add_middleware(PrometheusMiddleware, metrics=metrics)

    @app.get("/metrics")
    async def metrics_endpoint(request: Request) -> Response:
        """
        Exposes the Prometheus metrics endpoint.
        """
        registry = request.app.state.prometheus_metrics.registry
        return Response(
            content=prometheus_client.generate_latest(registry),
            media_type="text/plain",
        )
