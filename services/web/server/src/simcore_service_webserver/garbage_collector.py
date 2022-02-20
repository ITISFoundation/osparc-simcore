import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .garbage_collector_task import run_background_task
from .projects.projects_db import setup_projects_db

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_GARBAGE_COLLECTOR",
    logger=logger,
)
def setup_garbage_collector(app: web.Application):

    ## project-api needs access to db
    setup_projects_db(app)

    app.cleanup_ctx.append(run_background_task)
