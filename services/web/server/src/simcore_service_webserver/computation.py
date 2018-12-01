"""
    Main entry-point for computational backend


    TODO: should be a central place where status of all services can be checked!
    It would be perhaps possible to execute some requests with less services?
    or could define different execution policies in case of services failures
"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_routing import (iter_path_operations,
                                     map_handlers_with_operations)

from . import computation_api
from .computation_config import CONFIG_SECTION_NAME, SERVICE_NAME
from .computation_subscribe import subscribe
from .rest_config import APP_OPENAPI_SPECS_KEY

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

    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = map_handlers_with_operations(
        {'start_pipeline': computation_api.start_pipeline,
        'update_pipeline': computation_api.update_pipeline},
        filter(lambda o: "/computation" in o[1], iter_path_operations(specs)),
        strict=True
    )
    app.router.add_routes(routes)

# alias
setup_computation = setup

__all__ = (
    "setup_computation"
)
