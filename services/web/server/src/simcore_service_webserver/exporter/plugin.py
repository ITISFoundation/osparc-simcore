import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from . import _handlers

_logger = logging.getLogger(__name__)


@app_setup_func(
    "simcore_service_webserver.exporter",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_EXPORTER",
    logger=_logger,
)
def setup_exporter(app: web.Application) -> bool:

    # Rest-API routes: maps handlers with routes tags with "viewer" based on OAS operation_id
    app.router.add_routes(_handlers.routes)

    return True
