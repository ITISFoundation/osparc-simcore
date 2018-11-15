import logging
from typing import Dict

from aiohttp import web, ClientSession
from .application_keys import APP_CONFIG_KEY

# SETTINGS ----------------------------------------------------
THIS_SERVICE_NAME = 'storage'
APP_STORAGE_SESSION_KEY = __name__ + ".storage_session"
# --------------------------------------------------------------

log = logging.getLogger(__name__)


def get_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][THIS_SERVICE_NAME]

def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_STORAGE_SESSION_KEY]
