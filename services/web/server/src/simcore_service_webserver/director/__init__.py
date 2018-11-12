""" director subsystem

    Provides interactivity with the director service
"""

import logging

from aiohttp import web

from ..application_keys import APP_CONFIG_KEY
from .config import CONFIG_SECTION_NAME

logger = logging.getLogger(__name__)

def setup(app: web.Application):
    logger.debug("Setting up %s ...", __name__)

    assert CONFIG_SECTION_NAME in app[APP_CONFIG_KEY]


    # TODO: implement!!!



# alias
setup_director = setup

__all__ = (
    'setup_director'
)
