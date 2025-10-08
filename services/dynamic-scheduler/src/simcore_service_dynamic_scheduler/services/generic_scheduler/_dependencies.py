from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from ._core import Core
    from ._event_after import AfterEventManager
    from ._event_scheduler import EventScheduler

# NOTE:
# Due to circular dependencies it is not possible to use the following:
# - `Core.get_from_app_state(app)`
# - `AfterEventManager.get_from_app_state(app)`
# - `EventScheduler.get_from_app_state(app)`
# This module avoids issues with circular dependencies


def get_core(app: FastAPI) -> "Core":
    core: Core = app.state.generic_scheduler_core
    return core


def get_after_event_manager(app: FastAPI) -> "AfterEventManager":
    after_event_manager: AfterEventManager = app.state.after_event_manager
    return after_event_manager


def get_event_scheduler(app: FastAPI) -> "EventScheduler":
    event_scheduler: EventScheduler = app.state.generic_scheduler_event_scheduler
    return event_scheduler
