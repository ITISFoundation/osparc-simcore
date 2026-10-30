from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.long_running_tasks.long_running_client_helper import (
    LongRunningClientHelper,
)


def configure_long_running_tasks(app_lifespan: LifespanManager) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        long_running_client_helper = LongRunningClientHelper(redis_settings=app.state.settings.REDIS)
        await long_running_client_helper.setup()
        app.state.long_running_client_helper = long_running_client_helper
        try:
            yield
        finally:
            await long_running_client_helper.shutdown()

    app_lifespan.add(_lifespan)


def get_long_running_client_helper(app: FastAPI) -> LongRunningClientHelper:
    assert isinstance(app.state.long_running_client_helper, LongRunningClientHelper)  # nosec
    return app.state.long_running_client_helper
