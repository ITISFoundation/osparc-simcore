from aiohttp.web import Application
from .monitor import setup_monitor, shutdown_monitor, setup_api_client, shutdown_api_client
from .config import setup_settings


def setup_service_sidecar(app: Application):

    # on startup
    app.on_startup.append(setup_settings)
    app.on_startup.append(setup_api_client)
    app.on_startup.append(setup_monitor)

    app.on_shutdown.append(shutdown_monitor)
    app.on_shutdown.append(shutdown_api_client)
