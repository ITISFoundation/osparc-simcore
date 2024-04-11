import asyncio
import logging
from datetime import timedelta
from typing import Annotated, Final, cast
from uuid import uuid4

from fastapi import Depends, FastAPI
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from prometheus_client import CollectorRegistry, Gauge
from pydantic import PositiveFloat
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.fastapi.dependencies import get_app
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_api_server.models.schemas.jobs import JobID, JobLog
from simcore_service_api_server.services.log_streaming import LogDistributor

from .._meta import PROJECT_NAME

METRICS_NAMESPACE: Final[str] = PROJECT_NAME.replace("-", "_")

_logger = logging.getLogger(__name__)


class ApiServerHealthChecker:
    def __init__(
        self,
        *,
        registry: CollectorRegistry,
        log_distributor: LogDistributor,
        rabbit_client: RabbitMQClient,
        timeout_seconds: PositiveFloat,
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
        self._dummy_queue: asyncio.Queue[JobLog] = asyncio.Queue()
        self._dummy_message = LoggerRabbitMessage(
            user_id=UserID(456123),
            project_id=self._dummy_job_id,
            node_id=uuid4(),
            messages=["Api-server health check message"],
        )
        _logger.info("Api server health check dummy job_id=%s", f"{self._dummy_job_id}")

    async def setup(self, health_check_task_period_seconds: PositiveFloat):
        await self._log_distributor.register(
            job_id=self._dummy_job_id, queue=self._dummy_queue
        )
        self._background_task = start_periodic_task(
            task=self._background_task_method,
            interval=timedelta(seconds=health_check_task_period_seconds),
            task_name="api_server_health_check_task",
        )

    async def teardown(self, timeout_seconds: PositiveFloat):
        await stop_periodic_task(self._background_task, timeout=timeout_seconds)
        await self._log_distributor.deregister(job_id=self._dummy_job_id)

    @property
    def healthy(self) -> bool:
        return self._healthy

    def set_healthy(self, value: bool):
        self._healthy = value

    async def _background_task_method(self):
        # update prometheus metrics
        self._logstreaming_queues.clear()
        log_queue_sizes = self._log_distributor.get_log_queue_sizes()
        for job_id, length in log_queue_sizes.items():
            self._logstreaming_queues.labels(job_id=job_id).set(length)

        # check health
        while self._dummy_queue.qsize() > 0:
            _ = self._dummy_queue.get_nowait()
        try:
            await asyncio.wait_for(
                self._rabbit_client.publish(
                    self._dummy_message.channel_name, self._dummy_message
                ),
                timeout=self._timeout_seconds,
            )
            _ = await asyncio.wait_for(
                self._dummy_queue.get(), timeout=self._timeout_seconds
            )
            self.set_healthy(True)
        except asyncio.TimeoutError:
            self.set_healthy(False)


def get_health_checker(
    app: Annotated[FastAPI, Depends(get_app)],
) -> ApiServerHealthChecker:
    assert (
        app.state.health_checker
    ), "Api-server healthchecker is not setup. Please check the configuration"  # nosec
    return cast(ApiServerHealthChecker, app.state.health_checker)
