import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from ._task_manager import setup_task_manager

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_CELERY",
    logger=_logger,
)
def setup_celery(app: web.Application):
    app.cleanup_ctx.append(setup_task_manager)
