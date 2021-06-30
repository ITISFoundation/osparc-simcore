from fastapi import FastAPI

from .client_api import setup_api_client, shutdown_api_client
from .monitor import setup_monitor, shutdown_monitor


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        await setup_api_client(app)
        await setup_monitor(app)

    async def on_shutdown() -> None:
        await shutdown_monitor(app)
        await shutdown_api_client(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
