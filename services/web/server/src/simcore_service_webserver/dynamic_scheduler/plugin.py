"""
Plugin to interact with the 'dynamic-scheduler' service
"""

import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..rabbitmq import setup_rabbitmq

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DYNAMIC_SCHEDULER",
    logger=_logger,
)
def setup_dynamic_scheduler(app: web.Application):
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_DYNAMIC_SCHEDULER
    _ = settings

    setup_rabbitmq(app)
