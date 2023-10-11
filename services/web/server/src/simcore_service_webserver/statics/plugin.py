""" Serves client's code

    - The client-side runs a RIA (Rich Interface Application) so the server does not
    need to render pages upon request but only serve once the code to the client.
    - The client application then interacts with the server via a http and/or socket API
    - The client application is under ``services/static-webserver/client`` and the ``webclient`` service
    is used to build it.
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import INDEX_RESOURCE_NAME
from ..products.plugin import setup_products
from ._events import create_cached_indexes, create_statics_json
from ._handlers import get_cached_frontend_index, get_statics_json
from .settings import StaticWebserverModuleSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_STATICWEB", logger=_logger
)
def setup_statics(app: web.Application) -> None:

    settings: StaticWebserverModuleSettings = get_plugin_settings(app)
    assert settings  # nosec

    setup_products(app)

    # serves information composed by making 4 http requests (once for each product)
    # to the index.html in each of the 4 product directories /osparc, /s4l, /s4llite, /s4lacad and /tis
    app.router.add_get("/", get_cached_frontend_index, name=INDEX_RESOURCE_NAME)

    # statics.json is computed here and contains information used
    # by the frontend to properly render the client
    app.router.add_get(
        "/static-frontend-data.json", get_statics_json, name="static_frontend_data"
    )

    # compute statics.json content
    app.on_startup.append(create_statics_json)

    # fetch all index.html for various frontends
    app.on_startup.append(create_cached_indexes)
