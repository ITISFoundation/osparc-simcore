import logging
from typing import cast

from fastapi import FastAPI
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.errors import RedisNotConnectedError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.redis_client_sdk = None
        settings: RedisSettings = app.state.settings.AUTOSCALING_REDIS
        redis_locks_dsn = settings.build_redis_dsn(RedisDatabase.LOCKS)
        app.state.redis_client_sdk = client = RedisClientSDK(redis_locks_dsn)
        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                connected = await client.ping()
                if not connected:
                    raise RedisNotConnectedError(dsn=redis_locks_dsn)

    async def on_shutdown() -> None:
        redis_client_sdk: None | RedisClientSDK = app.state.redis_client_sdk
        if redis_client_sdk:
            await redis_client_sdk.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)
