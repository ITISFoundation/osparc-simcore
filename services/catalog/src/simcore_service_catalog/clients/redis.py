from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.redis_lifespan import (
    redis_database_lifespan,
)
from servicelib.redis import RedisClientSDK

redis_client_lifespan = LifespanManager()
redis_client_lifespan.add(redis_database_lifespan)


@redis_client_lifespan.add
async def _redis_client_sdk_lifespan(
    app: FastAPI, state: State
) -> AsyncIterator[State]:
    app.state.redis_client_sdk = state["REDIS_CLIENT_SDK"]
    yield {}
    del app.state.redis_client_sdk


def get_redis_client(app: FastAPI) -> RedisClientSDK:
    return cast(RedisClientSDK, app.state.redis_client_sdk)
