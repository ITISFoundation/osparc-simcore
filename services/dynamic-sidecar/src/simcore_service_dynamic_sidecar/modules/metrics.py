from collections import deque
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Final

import arrow
from fastapi import FastAPI
from pydantic import BaseModel, Field, NonNegativeFloat, NonNegativeInt
from servicelib.sequences_utils import pairwise

_MAX_DEFAULT_METRICS_SCRAPE_INTERVAL: Final[NonNegativeFloat] = 60.0
_MIN_ELEMENTS: Final[NonNegativeInt] = 2
_MAX_PROMETHEUS_SAMPLES: Final[NonNegativeInt] = 5


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


class UserServiceCommand(BaseModel):
    container_name: str = Field(
        ..., description="container in which to run the command"
    )
    cli_command: Path = Field(..., description="command to run into the container")
    timeout: NonNegativeFloat = Field(
        ..., description="after this interval the command will be timed"
    )


class UserServicesMetrics:
    def __init__(self, user_service_command: UserServiceCommand) -> None:
        self.user_service_command: UserServiceCommand = user_service_command
        self._last_prometheus_query_times: deque[datetime] = deque(
            maxlen=_MAX_PROMETHEUS_SAMPLES
        )

    def metrics_endpoint_called(self) -> None:
        self._last_prometheus_query_times.append(arrow.now().datetime)


def setup_metrics(app: FastAPI) -> None:
    async def on_startup() -> None:
        # TODO: UserServiceCommand from somewhere
        app.state.settings.user_service_metrics = UserServicesMetrics()

    async def on_shutdown() -> None:
        ...

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
