from aiohttp.web import Application
from .monitor import setup_monitor, shutdown_monitor, setup_api_client
from .config import setup_settings


def setup_service_sidecar(app: Application):
    setup_api_client(app)
    setup_settings(app)

    app.on_startup.append(setup_monitor)
    app.on_shutdown.append(shutdown_monitor)
