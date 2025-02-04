from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from settings_library.redis import RedisDatabase

from ..redis import get_redis_client
from ._tracker import Tracker


async def lifespan_service_tracker(app: FastAPI) -> AsyncIterator[State]:
    app.state.service_tracker = Tracker(
        get_redis_client(app, RedisDatabase.DYNAMIC_SERVICES)
    )
    yield {}


def get_tracker(app: FastAPI) -> Tracker:
    tracker: Tracker = app.state.service_tracker
    return tracker
