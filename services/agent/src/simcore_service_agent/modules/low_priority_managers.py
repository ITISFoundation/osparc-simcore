from dataclasses import dataclass, field
from typing import cast

from fastapi import FastAPI

from .concurrency import LowPriorityHandlerManager


@dataclass
class LowPriorityManagers:
    volumes_cleanup: LowPriorityHandlerManager = field(
        default_factory=LowPriorityHandlerManager
    )


def get_low_priority_managers(app: FastAPI) -> LowPriorityManagers:
    return cast(LowPriorityManagers, app.state.low_priority_managers)


def setup(app: FastAPI) -> None:
    async def _on_startup() -> None:
        app.state.low_priority_managers = LowPriorityManagers()

    app.add_event_handler("startup", _on_startup)


__all__: tuple[str, ...] = (
    "get_low_priority_managers",
    "setup",
)
