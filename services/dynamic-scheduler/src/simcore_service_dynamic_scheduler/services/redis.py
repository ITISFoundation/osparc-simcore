from fastapi import FastAPI
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings


def setup_redis(app: FastAPI) -> None:
    settings: RedisSettings = app.state.settings.DYNAMIC_SCHEDULER_REDIS

    async def on_startup() -> None:
        redis_locks_dsn = settings.build_redis_dsn(RedisDatabase.LOCKS)
        app.state.redis_client_sdk = client = RedisClientSDK(redis_locks_dsn)
        await client.setup()

    async def on_shutdown() -> None:
        redis_client_sdk: None | RedisClientSDK = app.state.redis_client_sdk
        if redis_client_sdk:
            await redis_client_sdk.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    redis_client_sdk: RedisClientSDK = app.state.redis_client_sdk
    return redis_client_sdk
