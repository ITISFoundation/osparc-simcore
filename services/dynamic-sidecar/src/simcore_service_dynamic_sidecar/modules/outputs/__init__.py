from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager

from ._context import OutputsContext, configure_outputs_context
from ._manager import OutputsManager, configure_outputs_manager
from ._watcher import (
    configure_outputs_watcher,
    disable_event_propagation,
    enable_event_propagation,
    event_propagation_disabled,
)


def configure_outputs(app_lifespan: LifespanManager[FastAPI]) -> None:
    configure_outputs_context(app_lifespan)
    configure_outputs_manager(app_lifespan)
    configure_outputs_watcher(app_lifespan)


__all__: tuple[str, ...] = (
    "OutputsContext",
    "OutputsManager",
    "configure_outputs",
    "disable_event_propagation",
    "enable_event_propagation",
    "event_propagation_disabled",
)
