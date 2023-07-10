""" RESTful API for simcore_service_storage

"""
import logging

import openapi_core
import yaml
from aiohttp import web
from aiohttp.web import RouteDef, RouteTableDef
from aiohttp_swagger import setup_swagger
from servicelib.aiohttp.openapi import get_base_path
from servicelib.aiohttp.rest_middlewares import append_rest_middlewares

from . import (
    handlers_datasets,
    handlers_files,
    handlers_health,
    handlers_locations,
    handlers_simcore_s3,
)
from .constants import APP_OPENAPI_SPECS_KEY
from .handlers_files import UPLOAD_TASKS_KEY
from .resources import storage_resources

log = logging.getLogger(__name__)


def set_default_names(routes: RouteTableDef):
    for r in routes:
        if isinstance(r, RouteDef):
            r.kwargs.setdefault("name", r.handler.__name__)


def setup_rest(app: web.Application):
    """Setup the rest API module in the application in aiohttp fashion.

    - loads and validate openapi specs from a remote (e.g. apihub) or local location
    - connects openapi specs paths to handlers (see rest_routes.py)
    - enables error, validation and envelope middlewares on API routes


    IMPORTANT: this is a critical subsystem. Any failure should stop
    the system startup. It CANNOT be simply disabled & continue
    """
    log.debug("Setting up %s ...", __name__)

    spec_path = storage_resources.get_path("api/v0/openapi.yaml")
    with spec_path.open() as fh:
        spec_dict = yaml.safe_load(fh)
    api_specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())

    # validated openapi specs
    app[APP_OPENAPI_SPECS_KEY] = api_specs

    # Connects handlers

    for routes in [
        handlers_health.routes,
        handlers_locations.routes,
        handlers_datasets.routes,
        handlers_files.routes,
        handlers_simcore_s3.routes,
    ]:
        set_default_names(routes)
        app.router.add_routes(routes)
    # prepare container for upload tasks
    app[UPLOAD_TASKS_KEY] = {}

    log.debug(
        "routes:\n %s",
        "\n".join(
            f"\t{name}:{resource}"
            for name, resource in app.router.named_resources().items()
        ),
    )

    # Enable error, validation and envelop middleware on API routes
    base_path = get_base_path(api_specs)
    append_rest_middlewares(app, base_path)

    # Adds swagger doc UI
    setup_swagger(
        app,
        swagger_url="/dev/doc",
        swagger_from_file=str(spec_path),
        ui_version=3,
    )
