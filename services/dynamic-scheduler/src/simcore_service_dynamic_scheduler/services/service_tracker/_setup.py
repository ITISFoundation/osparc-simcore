from fastapi import FastAPI
from settings_library.redis import RedisDatabase

from ..redis import get_redis_client
from ._tracker import Tracker


def setup_service_tracker(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.service_tracker = Tracker(
            get_redis_client(app, RedisDatabase.DYNAMIC_SERVICES)
        )

    app.add_event_handler("startup", on_startup)


def get_tracker(app: FastAPI) -> Tracker:
    tracker: Tracker = app.state.service_tracker
    return tracker
