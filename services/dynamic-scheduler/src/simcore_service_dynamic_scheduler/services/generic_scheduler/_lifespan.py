from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ...core.settings import ApplicationSettings
from ._core import Core
from ._event_scheduler import EventScheduler
from ._lifecycle_protocol import SupportsLifecycle
from ._store import Store


async def generic_scheduler_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    store = Store(settings.DYNAMIC_SCHEDULER_REDIS)
    store.set_to_app_state(app)

    Core(app).set_to_app_state(app)

    event_scheduler = EventScheduler(app)
    event_scheduler.set_to_app_state(app)

    with_setup_protocol: list[SupportsLifecycle] = [event_scheduler, store]

    for component in with_setup_protocol:
        await component.setup()

    yield {}

    for component in with_setup_protocol:
        await component.shutdown()
