"""
    Main entry-point for computational backend


    TODO: should be a central place where status of all services can be checked!
    It would be perhaps possible to execute some requests with less services?
    or could define different execution policies in case of services failures
"""
import logging

from .comp_backend_subscribe import subscribe

_LOGGER = logging.getLogger(__file__)

def setup_computational_backend(app):
    _LOGGER.debug("Setting up %s ...", __name__)

    # subscribe to rabbit upon startup
    app.on_startup.append(subscribe)

    # TODO: add function to "unsubscribe"
    # app.on_cleanup.append(unsubscribe)
