from fastapi import FastAPI

from ._context import OutputsContext, setup_outputs_context
from ._manager import OutputsManager, setup_outputs_manager
from ._watcher import (
    disable_event_propagation,
    enable_event_propagation,
    event_propagation_disabled,
    setup_outputs_watcher,
)


def setup_outputs(app: FastAPI) -> None:
    setup_outputs_context(app)
    setup_outputs_manager(app)
    setup_outputs_watcher(app)


__all__: tuple[str, ...] = (
    "disable_event_propagation",
    "enable_event_propagation",
    "event_propagation_disabled",
    "OutputsContext",
    "OutputsManager",
    "setup_outputs",
)
