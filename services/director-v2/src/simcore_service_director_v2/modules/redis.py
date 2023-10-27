from fastapi import FastAPI
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings


def setup(app: FastAPI):
    async def on_startup() -> None:
        redis_settings: RedisSettings = app.state.settings.REDIS
        app.state.redis_client_sdk = redis_client_sdk = RedisClientSDK(
            redis_settings.build_redis_dsn(RedisDatabase.CACHES)
        )
        await redis_client_sdk.setup()

    async def on_shutdown() -> None:
        redis_client_sdk: RedisClientSDK = app.state.redis_client_sdk
        await redis_client_sdk.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client_sdk(app: FastAPI) -> RedisClientSDK:
    return app.state.redis_client_sdk
