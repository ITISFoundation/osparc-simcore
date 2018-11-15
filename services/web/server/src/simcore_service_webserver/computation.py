"""
    Main entry-point for computational backend


    TODO: should be a central place where status of all services can be checked!
    It would be perhaps possible to execute some requests with less services?
    or could define different execution policies in case of services failures
"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

from .computation_config import CONFIG_SECTION_NAME, SERVICE_NAME
from .computation_subscribe import subscribe

log = logging.getLogger(__file__)


def setup(app: web.Application):
    log.debug("Setting up %s [service: %s] ...", __name__, SERVICE_NAME)

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    if not cfg["enabled"]:
        log.warning("Service '%s' explicitly disabled in config", SERVICE_NAME)
        return

    # subscribe to rabbit upon startup
    # TODO: REmoved temporarily!
    # TODO: Define connection policies (e.g. {on-startup}, lazy). Could be defined in config-file
    app.on_startup.append(subscribe)

    # TODO: add function to "unsubscribe"
    # app.on_cleanup.append(unsubscribe)


# alias
setup_computation = setup

__all__ = (
    "setup_computation"
)
