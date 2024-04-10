import asyncio
import logging
from datetime import timedelta
from typing import Final, cast
from uuid import uuid4

from fastapi import FastAPI
from models_library.rabbitmq_messages import LoggerRabbitMessage
from prometheus_client import CollectorRegistry, Gauge
from pydantic import PositiveInt
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation as setup_rest_instrumentation,
)
from servicelib.fastapi.rabbitmq import get_rabbitmq_client
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.api.dependencies.rabbitmq import (
    get_log_distributor,
    wait_till_log_distributor_ready,
    wait_till_rabbitmq_ready,
)
from simcore_service_api_server.models.schemas.jobs import JobID, JobLog
from simcore_service_api_server.services.log_streaming import LogDistributor

from .._meta import PROJECT_NAME

METRICS_NAMESPACE: Final[str] = PROJECT_NAME.replace("-", "_")

_logger = logging.getLogger(__name__)


class ApiServerHealthChecker:
    def __init__(
        self,
        registry: CollectorRegistry,
        log_distributor: LogDistributor,
        rabbit_client: RabbitMQClient,
        timeout_seconds: int,
    ) -> None:
        self._registry = registry
        self._log_distributor: LogDistributor = log_distributor
        self._rabbit_client: RabbitMQClient = rabbit_client
        self._timeout_seconds = timeout_seconds

        self._logstreaming_queues = Gauge(
            "log_stream_queue_length",
            "#Logs in log streaming queue",
            ["job_id"],
            namespace=METRICS_NAMESPACE,
        )
        self._healthy: bool = True
        self._dummy_job_id: JobID = uuid4()
        self._dummy_queue: asyncio.Queue[JobLog] = asyncio.Queue(maxsize=1)
        self._dummy_message = LoggerRabbitMessage(
            user_id=0,
            project_id=self._dummy_job_id,
            node_id=uuid4(),
            messages=["dummy message"],
        )
        _logger.info("Api server health check dummy job_id=%s", f"{self._dummy_job_id}")

    async def setup(self, health_check_task_period_seconds: PositiveInt):
        await self._log_distributor.register(
            job_id=self._dummy_job_id, queue=self._dummy_queue
        )
        self._background_task = start_periodic_task(
            task=self._background_task_method,
            interval=timedelta(seconds=health_check_task_period_seconds),
            task_name="api_server_health_check_task",
        )

    async def teardown(self):
        await self._log_distributor.deregister(job_id=self._dummy_job_id)
        await stop_periodic_task(self._background_task)

    def healthy(self) -> bool:
        return self._healthy

    async def _background_task_method(self):
        # update prometheus metrics
        self._logstreaming_queues.clear()
        log_queue_sizes = self._log_distributor.get_log_queue_sizes()
        for job_id, length in log_queue_sizes.items():
            self._logstreaming_queues.labels(job_id=job_id).set(length)

        # check health
        while self._dummy_queue.qsize() > 0:
            _ = self._dummy_queue.get_nowait()
        await self._rabbit_client.publish(
            LoggerRabbitMessage.get_channel_name(), self._dummy_message
        )
        try:
            _ = await asyncio.wait_for(
                self._dummy_queue.get(), timeout=self._timeout_seconds
            )
            self._healthy = True
        except asyncio.TimeoutError:
            self._healthy = False


def setup_health_checker(app: FastAPI):
    instrumentator = setup_rest_instrumentation(app)

    async def on_startup() -> None:
        await wait_till_rabbitmq_ready(app)
        await wait_till_log_distributor_ready(app)
        app.state.health_checker = ApiServerHealthChecker(
            registry=instrumentator.registry,
            log_distributor=get_log_distributor(app),
            rabbit_client=get_rabbitmq_client(app),
            timeout_seconds=app.state.settings.API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS,
        )
        await app.state.health_checker.setup(
            app.state.settings.API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS
        )

    async def on_shutdown() -> None:
        assert app.state.health_checker  # nosec
        await app.state.health_checker.teardown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_healtch_checker(app: FastAPI) -> ApiServerHealthChecker:
    assert (
        app.state.health_checker
    ), "Api-server healthchecker is not setup. Please check the configuration"  # nosec
    return cast(ApiServerHealthChecker, app.state.health_checker)
