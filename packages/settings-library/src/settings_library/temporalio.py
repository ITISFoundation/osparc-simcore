from functools import cached_property
from typing import Annotated

from pydantic import Field

from .base import BaseCustomSettings
from .basic_types import PortInt


class TemporalioSettings(BaseCustomSettings):
    TEMPORALIO_HOST: Annotated[
        str,
        Field(description="Hostname of the Temporalio server gRPC endpoint"),
    ] = "temporal"

    TEMPORALIO_PORT: Annotated[
        PortInt,
        Field(description="Port of the Temporalio server gRPC endpoint"),
    ] = 7233

    TEMPORALIO_NAMESPACE: Annotated[
        str,
        Field(description="Temporalio namespace to use for workflows"),
    ] = "default"

    TEMPORALIO_TASK_QUEUE: Annotated[
        str,
        Field(description="Temporalio task queue name"),
    ] = "dynamic-scheduler"

    TEMPORALIO_WORKER_GRACEFUL_SHUTDOWN_TIMEOUT_S: Annotated[
        int,
        Field(
            description=(
                "Seconds the Temporalio worker waits for running activities to complete "
                "before cancelling them during shutdown. "
                "Must be less than docker-compose stop_grace_period for the service."
            ),
        ),
    ] = 30

    @cached_property
    def target_host(self) -> str:
        return f"{self.TEMPORALIO_HOST}:{self.TEMPORALIO_PORT}"
