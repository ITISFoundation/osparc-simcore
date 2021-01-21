from aiohttp.web import Application
from .monitor import setup_monitor, shutdown_monitor


def setup_exporter(app: Application):
    app.on_startup.append(setup_monitor)
    app.on_shutdown.append(shutdown_monitor)
