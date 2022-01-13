""" Subsystem to communicate with catalog service

"""
import logging
from typing import List, Optional

from aiohttp import web
from aiohttp.web_routedef import RouteDef
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import iter_path_operations
from yarl import URL

from . import catalog_api_handlers, catalog_client
from ._constants import APP_OPENAPI_SPECS_KEY, RQ_PRODUCT_KEY, X_PRODUCT_NAME_HEADER
from .catalog_client import (
    get_services_for_user_in_product,
    is_service_responsive,
    to_backend_service,
)
from .catalog_config import (
    KCATALOG_ORIGIN,
    KCATALOG_VERSION_PREFIX,
    assert_valid_config,
)
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required

logger = logging.getLogger(__name__)


## HANDLERS  ------------------------


@login_required
@permission_required("services.catalog.*")
async def _reverse_proxy_handler(request: web.Request) -> web.Response:
    """
        - Adds auth layer
        - Adds access layer
        - Forwards request to catalog service

    SEE https://gist.github.com/barrachri/32f865c4705f27e75d3b8530180589fb
    """
    user_id = request[RQT_USERID_KEY]

    # path & queries
    backend_url = to_backend_service(
        request.rel_url,
        request.app[KCATALOG_ORIGIN],
        request.app[KCATALOG_VERSION_PREFIX],
    )
    # FIXME: hack
    if "/services" in backend_url.path:
        backend_url = backend_url.update_query({"user_id": user_id})
    logger.debug("Redirecting '%s' -> '%s'", request.url, backend_url)

    # body
    raw: Optional[bytes] = None
    if request.can_read_body:
        raw = await request.read()

    # injects product discovered by middleware in headers
    fwd_headers = request.headers.copy()
    product_name = request[RQ_PRODUCT_KEY]
    fwd_headers.update({X_PRODUCT_NAME_HEADER: product_name})

    # forward request
    return await catalog_client.make_request_and_envelope_response(
        request.app, request.method, backend_url, fwd_headers, raw
    )


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
    for route_def in catalog_api_handlers.routes:
        route_def.kwargs["name"] = operation_id = route_def.handler.__name__
        exclude.append(operation_id)

    app.add_routes(catalog_api_handlers.routes)

    # bind the rest routes with the reverse-proxy-handler
    # FIXME: this would reroute **anything** to the catalog service!
    handler = (
        _reverse_proxy_handler.__wrapped__ if disable_auth else _reverse_proxy_handler
    )
    routes = [
        web.route(method.upper(), path, handler, name=operation_id)
        for method, path, operation_id, tags in iter_path_operations(specs)
        if "catalog" in tags and operation_id not in exclude
    ]
    assert routes, "Got no paths tagged as catalog"  # nosec

    # reverse proxy to catalog's API
    app.router.add_routes(routes)


__all__ = ("get_services_for_user_in_product", "is_service_responsive", "setup_catalog")
