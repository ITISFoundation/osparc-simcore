""" RESTful API for simcore_service_storage

"""
import logging
from pathlib import Path

from aiohttp import web
from aiohttp_swagger import setup_swagger
from servicelib.aiohttp.rest_middlewares import append_rest_middlewares
from servicelib.aiohttp.rest_utils import (
    get_named_routes_as_message,
    set_default_route_names,
)

from . import (
    handlers_datasets,
    handlers_files,
    handlers_health,
    handlers_locations,
    handlers_simcore_s3,
)
from ._meta import api_vtag
from .handlers_files import UPLOAD_TASKS_KEY
from .resources import storage_resources

_logger = logging.getLogger(__name__)


def setup_rest(app: web.Application):
    """Setup the rest API module in the application in aiohttp fashion.

    - loads and validate openapi specs from a remote (e.g. apihub) or local location
    - connects openapi specs paths to handlers (see rest_routes.py)
    - enables error, validation and envelope middlewares on API routes


    IMPORTANT: this is a critical subsystem. Any failure should stop
    the system startup. It CANNOT be simply disabled & continue
    """
    _logger.debug("Setting up %s ...", __name__)

    spec_path: Path = storage_resources.get_path("api/v0/openapi.yaml")

    # Connects handlers
    for routes in [
        handlers_health.routes,
        handlers_locations.routes,
        handlers_datasets.routes,
        handlers_files.routes,
        handlers_simcore_s3.routes,
    ]:
        set_default_route_names(routes)
        app.router.add_routes(routes)

    _logger.debug("routes: %s", get_named_routes_as_message(app))

    # prepare container for upload tasks
    app[UPLOAD_TASKS_KEY] = {}

    # Enable error, validation and envelop middleware on API routes
    append_rest_middlewares(app, api_version=f"/{api_vtag}")

    # Adds swagger doc UI
    setup_swagger(
        app,
        swagger_url="/dev/doc",
        swagger_from_file=f"{spec_path}",
        ui_version=3,
    )
