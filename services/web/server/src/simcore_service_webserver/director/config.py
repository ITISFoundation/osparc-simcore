""" director subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

import trafaret as T
from aiohttp import ClientSession, web

from servicelib.application_keys import APP_CONFIG_KEY

APP_STORAGE_SESSION_KEY = __name__ + ".director_session"
CONFIG_SECTION_NAME = 'director'

schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Bool(),
    T.Key("host", default="director", ): T.String(),
    T.Key("port", default=8001): T.Int()
})

def get_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_STORAGE_SESSION_KEY]
