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

from . import rest_routes
from ._meta import api_version_prefix
from .constants import APP_OPENAPI_SPECS_KEY
from .diagnostics_config import get_diagnostics_config
from .rest_config import assert_valid_config
from .rest_utils import get_openapi_specs_path, load_openapi_specs

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.security"],
    logger=log,
)
def setup_rest(app: web.Application, *, swagger_doc_enabled: bool = True):
    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    cfg = assert_valid_config(app)
    # ---------------------------------------------

    api_version_dir = cfg["version"]
    spec_path = get_openapi_specs_path(api_version_dir)

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

    # diagnostics routes
    routes = rest_routes.create(specs)
    app.router.add_routes(routes)

    # middlewares
    # NOTE: using safe get here since some tests use incomplete configs
    is_diagnostics_enabled = get_diagnostics_config(app).get("enabled", False)
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
    if swagger_doc_enabled:
        setup_swagger(
            app,
            swagger_url="/dev/doc",
            swagger_from_file=str(spec_path),
            ui_version=3,
        )


__all__: Tuple[str, ...] = ("setup_rest",)
