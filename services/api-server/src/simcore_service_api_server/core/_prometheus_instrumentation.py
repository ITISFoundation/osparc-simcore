import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final, cast

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, Gauge
from pydantic import PositiveInt
from servicelib.background_task import create_periodic_task, stop_periodic_task
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation as setup_rest_instrumentation,
)
from servicelib.logging_utils import log_catch

from .._meta import PROJECT_NAME
from ..api.dependencies.rabbitmq import (
    get_log_distributor,
    wait_till_log_distributor_ready,
)
from ..core.health_checker import get_health_checker
from ..models.schemas.jobs import JobID

_logger = logging.getLogger(__name__)
METRICS_NAMESPACE: Final[str] = PROJECT_NAME.replace("-", "_")


@dataclass(slots=True, kw_only=True)
class ApiServerPrometheusInstrumentation:
    registry: CollectorRegistry
    _logstreaming_queues: Gauge = field(init=False)
    _health_check_qauge: Gauge = field(init=False)

    def __post_init__(self) -> None:
        self._logstreaming_queues = Gauge(
            "log_stream_queue_length",
            "#Logs in log streaming queue",
            ["job_id"],
            namespace=METRICS_NAMESPACE,
        )
        self._health_check_qauge = Gauge(
            "log_stream_health_check",
            "#Failures of log stream health check",
            namespace=METRICS_NAMESPACE,
        )

    def update_metrics(
        self, log_queue_sizes: dict[JobID, int], health_check_failure_count: PositiveInt
    ):
        self._health_check_qauge.set(health_check_failure_count)
        self._logstreaming_queues.clear()
        for job_id, length in log_queue_sizes.items():
            self._logstreaming_queues.labels(job_id=job_id).set(length)


async def _collect_prometheus_metrics_task(app: FastAPI):
    get_instrumentation(app).update_metrics(
        log_queue_sizes=get_log_distributor(app).get_log_queue_sizes,
        health_check_failure_count=get_health_checker(app).health_check_failure_count,
    )


def setup_prometheus_instrumentation(app: FastAPI):
    instrumentator = setup_rest_instrumentation(app)

    async def on_startup() -> None:
        app.state.instrumentation = ApiServerPrometheusInstrumentation(
            registry=instrumentator.registry
        )
        await wait_till_log_distributor_ready(app)
        app.state.instrumentation_task = create_periodic_task(
            task=_collect_prometheus_metrics_task,
            interval=timedelta(
                seconds=app.state.settings.API_SERVER_PROMETHEUS_INSTRUMENTATION_COLLECT_SECONDS
            ),
            task_name="prometheus_metrics_collection_task",
            app=app,
        )

    async def on_shutdown() -> None:
        assert app.state.instrumentation_task  # nosec
        with log_catch(_logger, reraise=False):
            await stop_periodic_task(app.state.instrumentation_task)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_instrumentation(app: FastAPI) -> ApiServerPrometheusInstrumentation:
    assert (
        app.state.instrumentation
    ), "Instrumentation not setup. Please check the configuration"  # nosec
    return cast(ApiServerPrometheusInstrumentation, app.state.instrumentation)
