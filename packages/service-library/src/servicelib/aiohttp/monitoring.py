"""Enables monitoring of some quantities needed for diagnostics"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Final

from aiohttp import web
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)
from prometheus_client.registry import CollectorRegistry

from ..common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from ..logging_utils import log_catch
from ..prometheus_metrics import (
    PrometheusMetrics,
    get_prometheus_metrics,
    record_request_metrics,
    record_response_metrics,
)
from .typing_extension import Handler

log = logging.getLogger(__name__)

_PROMETHEUS_METRICS: Final[str] = f"{__name__}.prometheus_metrics"  # noqa: N816


def get_collector_registry(app: web.Application) -> CollectorRegistry:
    metrics = app[_PROMETHEUS_METRICS]
    assert isinstance(metrics, PrometheusMetrics)  # nosec
    return metrics.registry


async def metrics_handler(request: web.Request):
    registry = get_collector_registry(request.app)

    # NOTE: Cannot use ProcessPoolExecutor because registry is not pickable
    result = await request.loop.run_in_executor(None, generate_latest, registry)
    response = web.Response(body=result)
    response.content_type = CONTENT_TYPE_LATEST
    return response


EnterMiddlewareCB = Callable[[web.Request], Awaitable[None]]
ExitMiddlewareCB = Callable[[web.Request, web.StreamResponse], Awaitable[None]]


def middleware_factory(
    app_name: str,
    enter_middleware_cb: EnterMiddlewareCB | None,
    exit_middleware_cb: ExitMiddlewareCB | None,
):
    @web.middleware
    async def middleware_handler(request: web.Request, handler: Handler):
        # See https://prometheus.io/docs/concepts/metric_types

        log_exception: BaseException | None = None
        resp: web.StreamResponse = web.HTTPInternalServerError(
            reason="Unexpected exception"
        )
        canonical_endpoint = request.path
        if request.match_info.route.resource:
            canonical_endpoint = request.match_info.route.resource.canonical
        start_time = perf_counter()
        try:
            if enter_middleware_cb:
                with log_catch(logger=log, reraise=False):
                    await enter_middleware_cb(request)

            metrics = request.app[_PROMETHEUS_METRICS]
            assert isinstance(metrics, PrometheusMetrics)  # nosec

            user_agent = request.headers.get(
                X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
            )

            with record_request_metrics(
                metrics=metrics,
                method=request.method,
                endpoint=canonical_endpoint,
                user_agent=user_agent,
            ):
                resp = await handler(request)

            assert isinstance(  # nosec
                resp, web.StreamResponse
            ), "Forgot envelope middleware?"

        except web.HTTPServerError as exc:
            resp = exc
            log_exception = exc
            raise resp from exc
        except web.HTTPException as exc:
            resp = exc
            log_exception = None
            raise resp from exc
        except asyncio.CancelledError as exc:
            resp = web.HTTPInternalServerError(text=f"{exc}")
            log_exception = exc
            raise resp from exc
        except Exception as exc:  # pylint: disable=broad-except
            resp = web.HTTPInternalServerError(text=f"{exc}")
            resp.__cause__ = exc
            log_exception = exc
            raise resp from exc

        finally:
            response_latency_seconds = perf_counter() - start_time

            record_response_metrics(
                metrics=metrics,
                method=request.method,
                endpoint=canonical_endpoint,
                user_agent=user_agent,
                http_status=resp.status,
                response_latency_seconds=response_latency_seconds,
            )

            if exit_middleware_cb:
                with log_catch(logger=log, reraise=False):
                    await exit_middleware_cb(request, resp)

            if log_exception:
                log.error(
                    'Unexpected server error "%s" from access: %s "%s %s" done '
                    "in %3.2f secs. Responding with status %s",
                    type(log_exception),
                    request.remote,
                    request.method,
                    request.path,
                    response_latency_seconds,
                    resp.status,
                    exc_info=log_exception,
                    stack_info=True,
                )

        return resp

    setattr(  # noqa: B010
        middleware_handler, "__middleware_name__", f"{__name__}.monitor_{app_name}"
    )

    return middleware_handler


def setup_monitoring(
    app: web.Application,
    app_name: str,
    *,
    enter_middleware_cb: EnterMiddlewareCB | None = None,
    exit_middleware_cb: ExitMiddlewareCB | None = None,
):
    app[_PROMETHEUS_METRICS] = get_prometheus_metrics()

    # WARNING: ensure ERROR middleware is over this one
    #
    # non-API request/response (e.g /metrics, /x/*  ...)
    #                                 |
    # API request/response (/v0/*)    |
    #       |                         |
    #       |                         |
    #       v                         |
    # ===== monitoring-middleware =====
    # == rest-error-middlewarer ====  |
    # ==           ...            ==  |
    # == rest-envelope-middleware ==  v
    #
    #

    # ensures is first layer but cannot guarantee the order setup is applied
    app.middlewares.append(
        middleware_factory(
            app_name,
            enter_middleware_cb=enter_middleware_cb,
            exit_middleware_cb=exit_middleware_cb,
        ),
    )

    app.router.add_get("/metrics", metrics_handler)

    return True
