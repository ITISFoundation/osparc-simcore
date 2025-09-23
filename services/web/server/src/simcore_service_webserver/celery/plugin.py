import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._task_manager import setup_task_manager

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_CELERY", logger=_logger
)
def setup_celery(app: web.Application):
    app.cleanup_ctx.append(setup_task_manager)
