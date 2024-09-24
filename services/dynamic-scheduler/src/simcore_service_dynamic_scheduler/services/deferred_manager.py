from fastapi import FastAPI
from servicelib.deferred_tasks import DeferredManager
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase

from .redis import get_redis_client


def setup_deferred_manager(app: FastAPI) -> None:
    async def on_startup() -> None:
        rabbit_settings: RabbitSettings = app.state.settings.DYNAMIC_SCHEDULER_RABBITMQ

        redis_client_sdk = get_redis_client(app, RedisDatabase.DEFERRED_TASKS)
        app.state.deferred_manager = manager = DeferredManager(
            rabbit_settings, redis_client_sdk, globals_context={"app": app}
        )
        await manager.setup()

    async def on_shutdown() -> None:
        manager: DeferredManager = app.state.deferred_manager
        await manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
