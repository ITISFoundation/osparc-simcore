""" Subsystem to communicate with catalog service

"""
import logging

from aiohttp import web
from aiohttp.web_routedef import RouteDef
from pint import UnitRegistry
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import iter_path_operations

from .._constants import APP_OPENAPI_SPECS_KEY
from . import _handlers
from ._handlers_reverse_proxy import reverse_proxy_handler
from .client import get_services_for_user_in_product, is_catalog_service_responsive

logger = logging.getLogger(__name__)


assert get_services_for_user_in_product  # nosec
assert is_catalog_service_responsive  # nosec


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_CATALOG",
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup_catalog(app: web.Application):
    # TODO: remove option disable_auth and replace by mocker.patch

    # resolve url
    exclude: list[str] = []
    route_def: RouteDef
    for route_def in _handlers.routes:
        route_def.kwargs["name"] = operation_id = route_def.handler.__name__
        exclude.append(operation_id)

    app.add_routes(_handlers.routes)

    # bind the rest routes with the reverse-proxy-handler
    specs = app[APP_OPENAPI_SPECS_KEY]  # validated openapi specs
    routes = [
        web.route(method.upper(), path, reverse_proxy_handler, name=operation_id)
        for method, path, operation_id, tags in iter_path_operations(specs)
        if "catalog" in tags and operation_id not in exclude
    ]
    assert routes, "Got no paths tagged as catalog"  # nosec

    # reverse proxy to catalog's API
    app.router.add_routes(routes)

    # prepares units registry
    app[UnitRegistry.__name__] = UnitRegistry()


__all__ = (
    "get_services_for_user_in_product",
    "is_catalog_service_responsive",
    "setup_catalog",
)
