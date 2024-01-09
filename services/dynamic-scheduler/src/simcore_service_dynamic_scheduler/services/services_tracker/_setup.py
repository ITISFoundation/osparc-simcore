from fastapi import FastAPI
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase

from ...core.settings import ApplicationSettings
from ._tracker import ServicesTracker


def setup_services_tracker(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings

        app.state.services_tracker = services_tracker = ServicesTracker(
            app,
            RedisClientSDK(
                settings.DYNAMIC_SCHEDULER_REDIS.build_redis_dsn(
                    RedisDatabase.DISTRIBUTED_IDENTIFIERS
                )
            ),
        )

        await services_tracker.setup()

    async def on_shutdown() -> None:
        services_tracker: ServicesTracker = app.state.services_tracker
        await services_tracker.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_services_tracker(app: FastAPI) -> ServicesTracker:
    services_tracker: ServicesTracker = app.state.services_tracker
    return services_tracker
