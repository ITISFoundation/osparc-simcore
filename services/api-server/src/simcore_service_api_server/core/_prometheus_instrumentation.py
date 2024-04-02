import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Final, cast

from attr import field
from fastapi import FastAPI
from prometheus_client import CollectorRegistry, Gauge
from pydantic import PositiveInt
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation as setup_rest_instrumentation,
)
from simcore_service_api_server.api.dependencies.rabbitmq import (
    get_log_distributor,
    wait_till_log_distributor_ready,
)
from simcore_service_api_server.models.schemas.jobs import JobID

from .._meta import PROJECT_NAME

METRICS_NAMESPACE: Final[str] = PROJECT_NAME.replace("-", "_")


@dataclass(slots=True, kw_only=True)
class ApiServerPrometheusInstrumentation:
    registry: CollectorRegistry
    _logstreaming_queues: Gauge = field(init=False)

    def __post_init__(self) -> None:
        self._logstreaming_queues = Gauge(
            "log_stream_queue_length",
            "#Logs in log streaming queue",
            ["job_id"],
            namespace=METRICS_NAMESPACE,
        )

    def update_metrics(self, log_queue_sizes: dict[JobID, int]):
        self._logstreaming_queues.clear()
        for job_id, length in log_queue_sizes.items():
            self._logstreaming_queues.labels(job_id=job_id).set(length)


async def _collect_prometheus_metrics_task(app: FastAPI):
    metrics_collect_seconds: PositiveInt = (
        app.state.settings.API_SERVER_PROMETHEUS_INSTRUMENTATION_COLLECT_SECONDS
    )
    assert (  # nosec
        app.state.instrumentation
    ), "Instrumentation not setup. Please check the configuration"
    instrumentation = get_instrumentation(app)
    await wait_till_log_distributor_ready(app)
    log_distributor = get_log_distributor(app)
    while True:
        await asyncio.sleep(metrics_collect_seconds)
        instrumentation.update_metrics(
            log_queue_sizes=log_distributor.get_log_queue_sizes()
        )


def setup_prometheus_instrumentation(app: FastAPI):
    instrumentator = setup_rest_instrumentation(app)

    async def on_startup() -> None:
        app.state.instrumentation = ApiServerPrometheusInstrumentation(
            registry=instrumentator.registry
        )
        app.state.instrumentation_task = start_periodic_task(
            task=partial(_collect_prometheus_metrics_task, app),
            interval=app.state.settings.API_SERVER_PROMETHEUS_INSTRUMENTATION_COLLECT_SECONDS,
            task_name="prometheus_metrics_collection_task",
        )

    async def on_shutdown() -> None:
        assert app.state.instrumentation_task  # nosec
        await stop_periodic_task(app.state.instrumentation_task)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_instrumentation(app: FastAPI) -> ApiServerPrometheusInstrumentation:
    assert (
        app.state.instrumentation
    ), "Instrumentation not setup. Please check the configuration"  # nosec
    return cast(ApiServerPrometheusInstrumentation, app.state.instrumentation)
