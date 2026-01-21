from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ...core.settings import ApplicationSettings
from ._operations import profiles, registry
from ._redis import RedisStore


async def scheduler_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings

    store = RedisStore(settings.DYNAMIC_SCHEDULER_REDIS)
    store.set_to_app_state(app)

    profiles.register_profiles()
    registry.register_operataions()

    await store.setup()

    yield {}

    await store.shutdown()
    registry.unregister_operations()
    profiles.unregister_profiles()
