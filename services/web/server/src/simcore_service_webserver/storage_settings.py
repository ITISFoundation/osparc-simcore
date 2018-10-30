import logging
from typing import Dict

from aiohttp import web
from .application_keys import APP_CONFIG_KEY

# SETTINGS ----------------------------------------------------
THIS_SERVICE_NAME = 'storage'

# --------------------------------------------------------------

log = logging.getLogger(__name__)


def get_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][THIS_SERVICE_NAME]
