# pylint: disable=R0902
import asyncio
import logging
from datetime import timedelta
from typing import Annotated, Final, cast
from uuid import uuid4

from fastapi import Depends, FastAPI
from models_library.rabbitmq_messages import LoggerRabbitMessage
from models_library.users import UserID
from pydantic import NonNegativeInt, PositiveFloat, PositiveInt
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.fastapi.dependencies import get_app
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RabbitMQClient

from .._meta import PROJECT_NAME
from ..models.schemas.jobs import JobID, JobLog
from ..services.log_streaming import LogDistributor

METRICS_NAMESPACE: Final[str] = PROJECT_NAME.replace("-", "_")

_logger = logging.getLogger(__name__)


class ApiServerHealthChecker:
    def __init__(
        self,
        *,
        log_distributor: LogDistributor,
        rabbit_client: RabbitMQClient,
        timeout_seconds: PositiveFloat,
        allowed_health_check_failures: PositiveInt,
    ) -> None:
        self._log_distributor: LogDistributor = log_distributor
        self._rabbit_client: RabbitMQClient = rabbit_client
        self._timeout_seconds = timeout_seconds
        self._allowed_health_check_failures = allowed_health_check_failures

        self._health_check_failure_count: NonNegativeInt = 0
        self._dummy_job_id: JobID = uuid4()
        self._dummy_queue: asyncio.Queue[JobLog] = asyncio.Queue()
        self._dummy_message = LoggerRabbitMessage(
            user_id=UserID(123456789),
            project_id=self._dummy_job_id,
            node_id=uuid4(),
            messages=["Api-server health check message"],
        )
        self._background_task: asyncio.Task | None = None
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

    async def teardown(self):
        if self._background_task:
            with log_catch(_logger, reraise=False):
                await stop_periodic_task(
                    self._background_task, timeout=self._timeout_seconds
                )
        await self._log_distributor.deregister(job_id=self._dummy_job_id)

    @property
    def healthy(self) -> bool:
        return self._rabbit_client.healthy and (
            self._health_check_failure_count <= self._allowed_health_check_failures
        )  # https://github.com/ITISFoundation/osparc-simcore/pull/6662

    @property
    def health_check_failure_count(self) -> NonNegativeInt:
        return self._health_check_failure_count

    def _increment_health_check_failure_count(self):
        self._health_check_failure_count += 1

    async def _background_task_method(self):
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
            self._health_check_failure_count = 0
        except asyncio.TimeoutError:
            self._increment_health_check_failure_count()


def get_health_checker(
    app: Annotated[FastAPI, Depends(get_app)],
) -> ApiServerHealthChecker:
    assert (
        app.state.health_checker
    ), "Api-server healthchecker is not setup. Please check the configuration"  # nosec
    return cast(ApiServerHealthChecker, app.state.health_checker)
