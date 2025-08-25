from fastapi import FastAPI
from servicelib.long_running_tasks.client_long_running_manager import (
    ClientLongRunningManager,
)


def setup(app: FastAPI):
    async def _on_startup() -> None:
        client_long_running_manager = app.state.client_long_running_manager = (
            ClientLongRunningManager(redis_settings=app.state.settings.REDIS)
        )
        await client_long_running_manager.setup()

    async def _on_shutdown() -> None:
        client_long_running_manager: ClientLongRunningManager = (
            app.state.client_long_running_manager
        )
        await client_long_running_manager.shutdown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_client_long_running_manager(app: FastAPI) -> ClientLongRunningManager:
    assert isinstance(
        app.state.client_long_running_manager, ClientLongRunningManager
    )  # nosec
    return app.state.client_long_running_manager
