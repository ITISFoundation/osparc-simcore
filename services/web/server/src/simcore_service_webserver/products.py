"""
This framework can serve different variants of the front-end client denoted 'products'

A product can be customized using settings defined in the backend (see products pg table).
Some of these are also transmitted to the front-end client via statics (see statis_settings.py)

At every request to this service API, a middleware discovers which product is the requester and sets the appropriate product context

"""


import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._constants import APP_PRODUCTS_KEY, APP_SETTINGS_KEY, RQ_PRODUCT_KEY
from .products_db import Product, load_products_from_db
from .products_middleware import discover_product_middleware

log = logging.getLogger(__name__)


def get_product_name(request: web.Request) -> str:
    return request[RQ_PRODUCT_KEY]


def get_current_product(request: web.Request) -> Product:
    """Returns product associated to current request"""
    product_name = get_product_name(request)
    return request.app[APP_PRODUCTS_KEY][product_name]


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.db"],
    settings_name="WEBSERVER_PRODUCTS",
    logger=log,
)
def setup_products(app: web.Application):

    assert app[APP_SETTINGS_KEY].WEBSERVER_PRODUCTS is True  # nosec

    app.middlewares.append(discover_product_middleware)
    app.on_startup.append(load_products_from_db)


# plugin API
__all__: tuple[str, ...] = (
    "get_current_product",
    "get_product_name",
    "Product",
    "setup_products",
)
