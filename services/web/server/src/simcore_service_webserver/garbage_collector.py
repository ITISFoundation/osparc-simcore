import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .garbage_collector_core import start_background_task

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_GARBAGE_COLLECTOR",
    logger=logger,
)
def setup_garbage_collector(app: web.Application):
    app.cleanup_ctx.append(start_background_task)
