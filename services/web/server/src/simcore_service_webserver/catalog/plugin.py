""" Subsystem to communicate with catalog service

"""
import logging

from aiohttp import web
from pint import UnitRegistry
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _handlers
from ._handlers_reverse_proxy import reverse_proxy_handler

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_CATALOG",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_catalog(app: web.Application):
    # ensures routes are names that corresponds to function names
    for route_def in _handlers.routes:
        route_def.kwargs["name"] = route_def.handler.__name__  # type: ignore

    app.add_routes(_handlers.routes)

    # reverse proxy to catalog's API
    # bind the rest routes with the reverse-proxy-handler
    app.router.add_routes(
        [
            web.get(
                path="/v0/catalog/dags",
                handler=reverse_proxy_handler,
                name="list_catalog_dags",
            ),
            web.post(
                path="/v0/catalog/dags",
                handler=reverse_proxy_handler,
                name="create_catalog_dag",
            ),
            web.put(
                path="/v0/catalog/dags/{dag_id}",
                handler=reverse_proxy_handler,
                name="replace_catalog_dag",
            ),
            web.delete(
                path="/v0/catalog/dags/{dag_id}",
                handler=reverse_proxy_handler,
                name="delete_catalog_dag",
            ),
        ]
    )

    # prepares units registry
    app[UnitRegistry.__name__] = UnitRegistry()
