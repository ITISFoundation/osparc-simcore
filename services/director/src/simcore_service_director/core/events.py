from collections.abc import AsyncIterator

from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.lifespan_utils import Lifespan

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG


async def _banners_lifespan(_) -> AsyncIterator[State]:
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201
    yield {}
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201


def create_app_lifespan(logging_lifespan: Lifespan | None = None) -> LifespanManager:  # WARNING: order matters
    app_lifespan = LifespanManager()
    if logging_lifespan:
        app_lifespan.add(logging_lifespan)

    app_lifespan.add(_banners_lifespan)

    return app_lifespan
