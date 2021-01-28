from aiohttp.web import Application

from .config import setup_settings
from .monitor import (
    setup_api_client,
    setup_monitor,
    shutdown_api_client,
    shutdown_monitor,
)


def setup_service_sidecar(app: Application):

    # on startup
    app.on_startup.append(setup_settings)
    app.on_startup.append(setup_api_client)
    app.on_startup.append(setup_monitor)

    app.on_shutdown.append(shutdown_monitor)
    app.on_shutdown.append(shutdown_api_client)
