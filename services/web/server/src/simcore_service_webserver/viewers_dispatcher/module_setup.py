# TODO: move here studies_access.py

import logging

from aiohttp import web
from servicelib.application_setup import ModuleCategory, app_module_setup

logger = logging.getLogger(__name__)

@app_module_setup(
    "simcore_service_webserver.viewers_dispatcher", ModuleCategory.SYSTEM, logger=logger
)
def setup_viewers_dispatcher(app: web.Application) -> bool:
    raise NotImplementedError()
