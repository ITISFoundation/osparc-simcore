from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.deferred_tasks import DeferredManager
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase

from .redis import get_redis_client


async def lifespan_deferred_manager(app: FastAPI) -> AsyncIterator[State]:
    rabbit_settings: RabbitSettings = app.state.settings.DYNAMIC_SCHEDULER_RABBITMQ

    redis_client_sdk = get_redis_client(app, RedisDatabase.DEFERRED_TASKS)
    app.state.deferred_manager = manager = DeferredManager(
        rabbit_settings, redis_client_sdk, globals_context={"app": app}
    )
    await manager.setup()

    yield {}

    await manager.shutdown()
