"""
    Main entry-point for computational backend


    TODO: should be a central place where status of all services can be checked!
    It would be perhaps possible to execute some requests with less services?
    or could define different execution policies in case of services failures
"""
import logging

from .comp_backend_subscribe import (
    subscribe,
    SERVICE_NAME
)

log = logging.getLogger(__file__)


def setup_computational_backend(app):
    log.debug("Setting up %s [service: %s] ...", __name__, SERVICE_NAME)

    disable_services = app["config"].get("app", {}).get("disable_services",[])
    if SERVICE_NAME in disable_services:
        log.warning("Service '%s' explicitly disabled in config", SERVICE_NAME)
        return

    # subscribe to rabbit upon startup
    # TODO: REmoved temporarily!
    # TODO: Define connection policies (e.g. {on-startup}, lazy). Could be defined in config-file
    app.on_startup.append(subscribe)

    # TODO: add function to "unsubscribe"
    # app.on_cleanup.append(unsubscribe)
