from fastapi import FastAPI

from .client_api import setup_api_client, shutdown_api_client
from .scheduler import setup_scheduler, shutdown_scheduler


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        await setup_api_client(app)
        await setup_scheduler(app)

    async def on_shutdown() -> None:
        await shutdown_scheduler(app)
        await shutdown_api_client(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
