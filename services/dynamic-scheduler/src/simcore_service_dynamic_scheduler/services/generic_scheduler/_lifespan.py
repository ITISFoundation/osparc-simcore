from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ...core.settings import ApplicationSettings
from ._core import Core
from ._event_after import AfterEventManager
from ._event_scheduler import EventScheduler
from ._lifecycle_protocol import SupportsLifecycle
from ._store import Store


async def generic_scheduler_lifespan(app: FastAPI) -> AsyncIterator[State]:
    # store
    settings: ApplicationSettings = app.state.settings
    store = Store(settings.DYNAMIC_SCHEDULER_REDIS)
    store.set_to_app_state(app)

    # core
    Core(app).set_to_app_state(app)

    # after event manager
    AfterEventManager(app).set_to_app_state(app)

    # event scheduler
    event_scheduler = EventScheduler(app)
    event_scheduler.set_to_app_state(app)

    supports_lifecycle: list[SupportsLifecycle] = [event_scheduler, store]

    for instance in supports_lifecycle:
        await instance.setup()

    yield {}

    for instance in supports_lifecycle:
        await instance.shutdown()
