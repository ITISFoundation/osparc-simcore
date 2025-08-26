import asyncio
import logging
from collections import deque
from collections.abc import Sequence
from datetime import datetime
from typing import Final

import arrow
from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI, status
from models_library.callbacks_mapping import CallbacksMapping, UserServiceCommand
from pydantic import BaseModel, NonNegativeFloat, NonNegativeInt
from servicelib.container_utils import (
    ContainerExecContainerNotFoundError,
    run_command_in_container,
)
from servicelib.logging_utils import log_context
from servicelib.sequences_utils import pairwise

from ..models.shared_store import SharedStore

_logger = logging.getLogger(__name__)

_MAX_DEFAULT_METRICS_SCRAPE_INTERVAL: Final[NonNegativeFloat] = 60.0
_MIN_ELEMENTS: Final[NonNegativeInt] = 2
_MAX_PROMETHEUS_SAMPLES: Final[NonNegativeInt] = 5
_TASK_CANCELLATION_TIMEOUT_S: Final[NonNegativeInt] = 2

_USER_SERVICES_NOT_STARTED: Final[str] = "User service(s) was/were not started"


def _get_user_services_scrape_interval(
    last_prometheus_query_times: Sequence[datetime],
) -> NonNegativeFloat:
    if len(last_prometheus_query_times) < _MIN_ELEMENTS:
        return _MAX_DEFAULT_METRICS_SCRAPE_INTERVAL

    time_pairs: list[tuple[datetime, datetime]] = list(
        pairwise(last_prometheus_query_times)
    )
    scrape_intervals: list[NonNegativeFloat] = [
        (t2 - t1).total_seconds() for t1, t2 in time_pairs
    ]
    average_prometheus_scrape_interval = sum(scrape_intervals) / len(scrape_intervals)
    return min(average_prometheus_scrape_interval, _MAX_DEFAULT_METRICS_SCRAPE_INTERVAL)


class MetricsResponse(BaseModel):
    body: str
    status: int

    @staticmethod
    def __get_iso_timestamp() -> str:
        return f"{arrow.now().datetime.isoformat()}"

    @classmethod
    def from_reply(cls, metrics_fetch_result: str) -> "MetricsResponse":
        body = f"{metrics_fetch_result}"
        return cls(body=body, status=status.HTTP_200_OK)

    @classmethod
    def from_error(cls, error: Exception) -> "MetricsResponse":
        iso_timestamp = cls.__get_iso_timestamp()
        return cls(
            body=f"At {iso_timestamp} an unexpected error occurred: {error}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @classmethod
    def initial_response(cls) -> "MetricsResponse":
        return cls(body="", status=status.HTTP_200_OK)


class UserServicesMetrics:
    def __init__(
        self, shared_store: SharedStore, metrics_command: UserServiceCommand
    ) -> None:
        self.shared_store: SharedStore = shared_store
        self.metrics_command: UserServiceCommand = metrics_command

        self._last_prometheus_query_times: deque[datetime] = deque(
            maxlen=_MAX_PROMETHEUS_SAMPLES
        )
        self._metrics_recovery_task: asyncio.Task | None = None

        self._metrics_response: MetricsResponse = MetricsResponse.initial_response()

    def get_metrics(self) -> MetricsResponse:
        self._last_prometheus_query_times.append(arrow.now().datetime)
        return self._metrics_response

    async def _update_metrics(self):
        container_name: str | None = self.shared_store.original_to_container_names.get(
            self.metrics_command.service, None
        )
        if container_name is None:
            self._metrics_response = MetricsResponse.from_error(
                RuntimeError(_USER_SERVICES_NOT_STARTED)
            )
            return

        try:
            metrics_fetch_result = await run_command_in_container(
                container_name,
                command=self.metrics_command.command,
                timeout=self.metrics_command.timeout,
            )
            self._metrics_response = MetricsResponse.from_reply(metrics_fetch_result)
        except ContainerExecContainerNotFoundError as e:
            _logger.debug(
                "Container %s was not found could not recover metrics",
                container_name,
            )
            self._metrics_response = MetricsResponse.from_error(e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            _logger.debug("Could not recover metrics", exc_info=True)
            self._metrics_response = MetricsResponse.from_error(e)

    async def _task_metrics_recovery(self) -> None:
        while True:
            with log_context(_logger, logging.DEBUG, "prometheus metrics update"):
                await self._update_metrics()

                # NOTE: will wait at most `_MAX_DEFAULT_METRICS_SCRAPE_INTERVAL` before scraping
                # the metrics again.
                # If Prometheus is actively scraping this container, it will match it's
                # scraping rate to provide up to date metrics.
                await asyncio.sleep(
                    _get_user_services_scrape_interval(
                        self._last_prometheus_query_times
                    )
                )

    async def start(self) -> None:
        with log_context(_logger, logging.INFO, "setup service metrics recovery"):
            if self._metrics_recovery_task is None:
                self._metrics_recovery_task = asyncio.create_task(
                    self._task_metrics_recovery()
                )
            else:
                _logger.info("metrics recovery was already started")

    async def stop(self) -> None:
        with log_context(_logger, logging.INFO, "shutdown service metrics recovery"):
            if self._metrics_recovery_task:
                await cancel_wait_task(
                    self._metrics_recovery_task, max_delay=_TASK_CANCELLATION_TIMEOUT_S
                )


def setup_prometheus_metrics(app: FastAPI) -> None:
    async def on_startup() -> None:
        callbacks_mapping: CallbacksMapping = (
            app.state.settings.DY_SIDECAR_CALLBACKS_MAPPING
        )
        assert callbacks_mapping.metrics  # nosec

        with log_context(
            _logger, logging.INFO, "enabling user services metrics scraping"
        ):
            shared_store: SharedStore = app.state.shared_store
            app.state.user_service_metrics = user_service_metrics = UserServicesMetrics(
                shared_store, callbacks_mapping.metrics
            )
            await user_service_metrics.start()

    async def on_shutdown() -> None:
        user_service_metrics: UserServicesMetrics = app.state.user_service_metrics
        await user_service_metrics.stop()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
