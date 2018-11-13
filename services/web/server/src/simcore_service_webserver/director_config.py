""" director - subsystem's configuration

    - defines schema for this subsystem's section in configuration file
    - helpers functions to get/set configuration from app configuration

TODO: add validation, get/set app config
"""
from typing import Dict

import trafaret as T
from aiohttp import web

from .application_keys import APP_CONFIG_KEY


THIS_SERVICE_NAME = 'director'


schema = T.Dict({
    T.Key("host", default=THIS_SERVICE_NAME): T.String(),
    "port": T.Int()
})


def get_from(app: web.Application) -> Dict:
    """ Gets section from application's config

    """
    return app[APP_CONFIG_KEY][THIS_SERVICE_NAME]



# alias
DIRECTOR_SERVICE = THIS_SERVICE_NAME
director_schema = schema


__all__ = (
    "DIRECTOR_SERVICE",
    "director_schema"
)
