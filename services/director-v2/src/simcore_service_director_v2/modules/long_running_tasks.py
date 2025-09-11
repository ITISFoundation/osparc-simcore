from fastapi import FastAPI
from servicelib.long_running_tasks.long_running_client_helper import (
    LongRunningClientHelper,
)


def setup(app: FastAPI):
    async def _on_startup() -> None:
        long_running_client_helper = app.state.long_running_client_helper = (
            LongRunningClientHelper(redis_settings=app.state.settings.REDIS)
        )
        await long_running_client_helper.setup()

    async def _on_shutdown() -> None:
        long_running_client_helper: LongRunningClientHelper = (
            app.state.long_running_client_helper
        )
        await long_running_client_helper.shutdown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_long_running_client_helper(app: FastAPI) -> LongRunningClientHelper:
    assert isinstance(
        app.state.long_running_client_helper, LongRunningClientHelper
    )  # nosec
    return app.state.long_running_client_helper
