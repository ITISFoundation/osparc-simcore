import asyncio
import logging
from collections import deque
from collections.abc import Sequence
from datetime import datetime
from typing import Final

import arrow
from fastapi import FastAPI
from models_library.service_settings_labels import CallbacksMapping, UserServiceCommand
from pydantic import NonNegativeFloat, NonNegativeInt
from servicelib.background_task import cancel_task
from servicelib.logging_utils import log_context
from servicelib.sequences_utils import pairwise

from ..core.settings import ApplicationSettings
from .container_utils import run_command_in_container

_logger = logging.getLogger(__name__)

_MAX_DEFAULT_METRICS_SCRAPE_INTERVAL: Final[NonNegativeFloat] = 60.0
_MIN_ELEMENTS: Final[NonNegativeInt] = 2
_MAX_PROMETHEUS_SAMPLES: Final[NonNegativeInt] = 5
_TASK_CANCELLATION_TIMEOUT_S: Final[NonNegativeInt] = 2


def _get_user_services_scrape_interval(
    last_prometheus_query_times: Sequence[datetime],
) -> NonNegativeFloat:
    if len(last_prometheus_query_times) < _MIN_ELEMENTS:
        return _MAX_DEFAULT_METRICS_SCRAPE_INTERVAL

    time_paris: list[tuple[datetime, datetime]] = list(
        pairwise(last_prometheus_query_times)
    )
    scrape_intervals: list[NonNegativeFloat] = [
        (t2 - t1).total_seconds() for t1, t2 in time_paris
    ]
    average_prometheus_scrape_interval = sum(scrape_intervals) / len(scrape_intervals)
    return min(average_prometheus_scrape_interval, _MAX_DEFAULT_METRICS_SCRAPE_INTERVAL)


class UserServicesMetrics:
    def __init__(self, metrics_command: UserServiceCommand) -> None:
        self.metrics_command: UserServiceCommand = metrics_command
        self._last_prometheus_query_times: deque[datetime] = deque(
            maxlen=_MAX_PROMETHEUS_SAMPLES
        )
        self._metrics_recovery_task: asyncio.Task | None = None
        self._metrics: str = ""

    def get_metrics(self) -> str:
        self._last_prometheus_query_times.append(arrow.now().datetime)
        return self._metrics

    async def _update_metrics(self):
        self._metrics = await run_command_in_container(
            # TODO: PORT service name to container name
            self.metrics_command.service,
            command=self.metrics_command.command,
            timeout=self.metrics_command.timeout,
        )

    async def _task_metrics_recovery(self) -> None:
        while True:
            await self._update_metrics()

            # NOTE: will wait at most `_MAX_DEFAULT_METRICS_SCRAPE_INTERVAL` before scraping
            # the metrics again.
            # If Prometheus is actively scraping this container, it will match it's
            # scraping rate to provide up to date metrics.
            await asyncio.sleep(
                _get_user_services_scrape_interval(self._last_prometheus_query_times)
            )

    async def setup(self) -> None:
        with log_context(_logger, logging.INFO, "setup service metrics recovery"):
            self._metrics_recovery_task = asyncio.create_task(
                self._task_metrics_recovery()
            )

    async def shutdown(self) -> None:
        with log_context(_logger, logging.INFO, "shutdown service metrics recovery"):
            if self._metrics_recovery_task:
                await cancel_task(
                    self._metrics_recovery_task, timeout=_TASK_CANCELLATION_TIMEOUT_S
                )


def setup_metrics(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        callbacks_mapping: CallbacksMapping = settings.DY_SIDECAR_CALLBACKS_MAPPING

        if callbacks_mapping.metrics:
            with log_context(
                _logger, logging.INFO, "enabling user services metrics scraping"
            ):
                app.state.settings.user_service_metrics = (
                    user_service_metrics
                ) = UserServicesMetrics(callbacks_mapping.metrics)

                await user_service_metrics.setup()

    async def on_shutdown() -> None:
        user_service_metrics: UserServicesMetrics = (
            app.state.settings.user_service_metrics
        )
        await user_service_metrics.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
