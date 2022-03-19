""" Restful API

    - Loads and validates openapi specifications (oas)
    - Adds check and diagnostic routes
    - Activates middlewares

"""
import logging
from typing import Tuple

from aiohttp import web
from aiohttp_swagger import setup_swagger
from servicelib.aiohttp import openapi
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_middlewares import (
    envelope_middleware_factory,
    error_middleware_factory,
)

from . import rest_handlers
from ._constants import APP_OPENAPI_SPECS_KEY, APP_SETTINGS_KEY
from ._meta import API_VTAG, api_version_prefix
from .rest_settings import RestSettings, get_plugin_settings
from .rest_utils import get_openapi_specs_path, load_openapi_specs

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.security"],
    settings_name="WEBSERVER_REST",
    logger=log,
)
def setup_rest(app: web.Application):
    settings: RestSettings = get_plugin_settings(app)
    is_diagnostics_enabled: bool = (
        app[APP_SETTINGS_KEY].WEBSERVER_DIAGNOSTICS is not None
    )

    spec_path = get_openapi_specs_path(api_version_dir=API_VTAG)

    # validated openapi specs
    app[APP_OPENAPI_SPECS_KEY] = specs = load_openapi_specs(spec_path)

    # version check
    base_path = openapi.get_base_path(specs)
    major, *_ = specs.info.version

    if f"/v{major}" != base_path:
        raise ValueError(
            f"REST API basepath {base_path} does not fit openapi.yml version {specs.info.version}"
        )

    if api_version_prefix != f"v{major}":
        raise ValueError(
            f"__version__.api_version_prefix {api_version_prefix} does not fit openapi.yml version {specs.info.version}"
        )

    # basic routes
    app.add_routes(rest_handlers.routes)
    if not is_diagnostics_enabled:
        # NOTE: the healthcheck route is normally in diagnostics, but
        # if disabled, this plugin adds a simple version of it
        app.add_routes(
            [
                web.get(
                    path=f"/{api_version_prefix}/health",
                    handler=rest_handlers.check_running,
                    name="check_health",
                )
            ]
        )

    # middlewares
    # NOTE: using safe get here since some tests use incomplete configs
    app.middlewares.extend(
        [
            error_middleware_factory(
                api_version_prefix,
                log_exceptions=not is_diagnostics_enabled,
            ),
            envelope_middleware_factory(api_version_prefix),
        ]
    )

    # Adds swagger doc UI
    #  - API doc at /dev/doc (optional, e.g. for testing since it can be heavy)
    #  - NOTE: avoid /api/* since traeffik uses for it's own API
    #
    log.debug("OAS loaded from %s ", spec_path)
    if settings.REST_SWAGGER_API_DOC_ENABLED:
        setup_swagger(
            app,
            swagger_url="/dev/doc",
            swagger_from_file=str(spec_path),
            ui_version=3,
        )


__all__: Tuple[str, ...] = ("setup_rest",)
