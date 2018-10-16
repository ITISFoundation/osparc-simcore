""" RESTful API for simcore_service_storage

"""
import logging

from servicelib.rest_middlewares import (envelope_middleware,
                                                 error_middleware)

from . import rest_routings

log = logging.getLogger(__name__)


def setup_rest(app):
    """Setup the rest API module in the application in aiohttp fashion. """
    log.debug("Setting up %s ...", __name__)

    #Injects rest middlewares in the application
    app.middlewares.append(error_middleware)
    app.middlewares.append(envelope_middleware)

    rest_routings.setup(app)

__all__ = (
    'setup_rest'
)
