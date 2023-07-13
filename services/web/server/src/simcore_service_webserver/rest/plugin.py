""" Restful API

    - Loads and validates openapi specifications (oas)
    - Adds check and diagnostic routes
    - Activates middlewares

"""
import logging

from aiohttp import web
from aiohttp_swagger import setup_swagger
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_middlewares import (
    envelope_middleware_factory,
    error_middleware_factory,
)

from .._constants import APP_SETTINGS_KEY
from .._meta import API_VTAG
from ..security.plugin import setup_security
from . import _handlers
from ._utils import get_openapi_specs_path
from .healthcheck import HealthCheck
from .settings import RestSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.rest",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_REST",
    logger=_logger,
)
def setup_rest(app: web.Application):
    settings: RestSettings = get_plugin_settings(app)

    setup_security(app)

    is_diagnostics_enabled: bool = (
        app[APP_SETTINGS_KEY].WEBSERVER_DIAGNOSTICS is not None
    )

    spec_path = get_openapi_specs_path(api_version_dir=API_VTAG)

    app[HealthCheck.__name__] = HealthCheck(app)
    _logger.debug("Setup %s", f"{app[HealthCheck.__name__]=}")

    # basic routes
    app.add_routes(_handlers.routes)

    # middlewares
    # NOTE: using safe get here since some tests use incomplete configs
    app.middlewares.extend(
        [
            error_middleware_factory(
                api_version=API_VTAG,
                log_exceptions=not is_diagnostics_enabled,
            ),
            envelope_middleware_factory(api_version=API_VTAG),
        ]
    )

    # Adds swagger doc UI
    #  - API doc at /dev/doc (optional, e.g. for testing since it can be heavy)
    #  - NOTE: avoid /api/* since traeffik uses for it's own API
    #
    _logger.debug("OAS loaded from %s ", spec_path)
    if settings.REST_SWAGGER_API_DOC_ENABLED:
        setup_swagger(
            app,
            swagger_url="/dev/doc",
            swagger_from_file=str(spec_path),
            ui_version=3,
        )


__all__: tuple[str, ...] = ("setup_rest",)
