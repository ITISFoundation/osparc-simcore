from aiohttp.web import Application
from .monitor import setup_monitor, shutdown_monitor
from .config import setup_settings


def setup_exporter(app: Application):
    setup_settings(app)

    app.on_startup.append(setup_monitor)
    app.on_shutdown.append(shutdown_monitor)
