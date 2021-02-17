from aiohttp.web import Application

from .config import setup_settings
from .monitor import (
    setup_api_client,
    setup_monitor,
    shutdown_api_client,
    shutdown_monitor,
)


def setup_service_sidecar(app: Application) -> None:
    async def on_startup() -> None:
        await setup_settings(app)
        await setup_api_client(app)
        await setup_monitor(app)

    async def on_shutdown() -> None:
        await shutdown_monitor(app)
        await shutdown_api_client(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
