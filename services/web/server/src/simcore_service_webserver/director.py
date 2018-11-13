""" director - subsystem that communicates with director service

"""

import logging

from aiohttp import web

from . import director_config

logger = logging.getLogger(__name__)


# SETTINGS ----------------------------------------------------
THIS_MODULE_NAME = __name__.split(".")[-1]

# --------------------------------------------------------------



def setup(app: web.Application):
    """Setup the directory sub-system in the application a la aiohttp fashion

    """
    logger.debug("Setting up %s ...", __name__)

    _cfg = director_config.get_from(app)

    # TODO: create instance of director's client-sdk

    # TODO: inject in application




# alias
setup_director = setup

__all__ = (
    'setup_director'
)
