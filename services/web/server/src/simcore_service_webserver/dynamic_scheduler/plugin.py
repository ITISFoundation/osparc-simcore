"""
    Plugin to interact with the 'dynamic-scheduler' service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from simcore_service_webserver.rabbitmq import setup_rabbitmq

from ..constants import APP_SETTINGS_KEY

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DYNAMIC_SCHEDULER",
    logger=_logger,
)
def setup_dynamic_scheduler(app: web.Application):
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DYNAMIC_SCHEDULER
    _ = settings

    setup_rabbitmq(app)
