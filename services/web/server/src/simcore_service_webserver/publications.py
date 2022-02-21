""" publications management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    get_handlers_from_namespace,
    iter_path_operations,
    map_handlers_with_operations,
)

from . import publication_handlers
from ._constants import APP_OPENAPI_SPECS_KEY
from .email import setup_email

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    settings_name="WEBSERVER_PUBLICATIONS",
    logger=logger,
)
def setup_publications(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_PUBLICATIONS  # nosec

    setup_email(app)

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = map_handlers_with_operations(
        get_handlers_from_namespace(publication_handlers),
        filter(lambda o: "publication" in o[3], iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(routes)
