""" Subsystem to communicate with catalog service

"""
import logging
from typing import List, Tuple

from aiohttp import web
from aiohttp.web_routedef import RouteDef
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import iter_path_operations
from yarl import URL

from . import catalog__handlers
from ._constants import APP_OPENAPI_SPECS_KEY
from .catalog__handlers_revproxy import reverse_proxy_handler
from .catalog_client import KCATALOG_ORIGIN, KCATALOG_VERSION_PREFIX
from .catalog_config import assert_valid_config

logger = logging.getLogger(__name__)


## SETUP ------------------------


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup_catalog(app: web.Application, *, disable_auth=False):
    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    cfg = assert_valid_config(app).copy()
    # ---------------------------------------------

    # resolve url
    app[KCATALOG_ORIGIN] = URL.build(scheme="http", host=cfg["host"], port=cfg["port"])
    app[KCATALOG_VERSION_PREFIX] = cfg["version"]

    specs = app[APP_OPENAPI_SPECS_KEY]  # validated openapi specs

    exclude: List[str] = []
    route_def: RouteDef
    for route_def in catalog__handlers.routes:
        route_def.kwargs["name"] = operation_id = route_def.handler.__name__
        exclude.append(operation_id)

    app.add_routes(catalog__handlers.routes)

    # bind the rest routes with the reverse-proxy-handler
    # FIXME: this would reroute **anything** to the catalog service!
    handler = (
        reverse_proxy_handler.__wrapped__ if disable_auth else reverse_proxy_handler
    )
    routes = [
        web.route(method.upper(), path, handler, name=operation_id)
        for method, path, operation_id, tags in iter_path_operations(specs)
        if "catalog" in tags and operation_id not in exclude
    ]
    assert routes, "Got no paths tagged as catalog"  # nosec

    # reverse proxy to catalog's API
    app.router.add_routes(routes)


__all__: Tuple[str, ...] = ("setup_catalog",)
