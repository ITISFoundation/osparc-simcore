"""
This framework can serve different variants of the front-end client denoted 'products'

A product can be customized using settings defined in the backend (see products pg table).
Some of these are also transmitted to the front-end client via statics (see statis_settings.py)

At every request to this service API, a middleware discovers which product is the requester and sets the appropriate product context

"""


import logging
import os.path
from pathlib import Path

import aiofiles
from aiohttp import web
from models_library.products import ProductName
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_PRODUCTS_KEY, APP_SETTINGS_KEY, RQ_PRODUCT_KEY
from .._resources import webserver_resources
from ._db import ProductRepository
from ._events import (
    APP_PRODUCTS_TEMPLATES_DIR_KEY,
    auto_create_products_groups,
    load_products_on_startup,
    setup_product_templates,
)
from ._middlewares import discover_product_middleware
from ._model import Product

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.db"],
    settings_name="WEBSERVER_PRODUCTS",
    logger=log,
)
def setup_products(app: web.Application):

    assert app[APP_SETTINGS_KEY].WEBSERVER_PRODUCTS is True  # nosec

    # middlewares
    app.middlewares.append(discover_product_middleware)

    # events
    app.on_startup.append(
        # NOTE: must go BEFORE load_products_on_startup
        auto_create_products_groups
    )
    app.on_startup.append(load_products_on_startup)
    app.cleanup_ctx.append(setup_product_templates)


#
# helper functions with requests
#


def get_product_name(request: web.Request) -> str:
    product_name: str = request[RQ_PRODUCT_KEY]
    return product_name


def get_current_product(request: web.Request) -> Product:
    """Returns product associated to current request"""
    product_name: ProductName = get_product_name(request)
    current_product: Product = request.app[APP_PRODUCTS_KEY][product_name]
    return current_product


def list_products(app: web.Application) -> list[Product]:
    products: list[Product] = app[APP_PRODUCTS_KEY].values()
    return products


async def get_product_template_path(request: web.Request, filename: str) -> Path:
    def _themed(dirname, template) -> Path:
        path: Path = webserver_resources.get_path(os.path.join(dirname, template))
        return path

    async def _get_content(template_name: str):
        repo = ProductRepository(request)
        content = await repo.get_template_content(template_name)
        if not content:
            raise ValueError(f"Missing template {template_name} for product")
        return content

    def _safe_get_current_product(request: web.Request) -> Product | None:
        try:
            product: Product = get_current_product(request)
            return product
        except KeyError:
            return None

    # ---
    if product := _safe_get_current_product(request):
        if template_name := product.get_template_name_for(filename):
            template_dir: Path = request.app[APP_PRODUCTS_TEMPLATES_DIR_KEY]
            template_path = template_dir / template_name
            if not template_path.exists():
                # cache
                content = await _get_content(template_name)
                try:
                    async with aiofiles.open(template_path, "wt") as fh:
                        await fh.write(content)
                except Exception:
                    # fails to write
                    if template_path.exists():
                        template_path.unlink()
                    raise

            return template_path

        # check static resources under templates/
        if (
            template_path := _themed(f"templates/{product.name}", filename)
        ) and template_path.exists():
            return template_path

    # If no product or template for product defined, we fall back to common templates
    common_template = _themed("templates/common", filename)
    if not common_template.exists():
        raise ValueError(f"{filename} is not part of the templates/common")

    return common_template


__all__: tuple[str, ...] = (
    "get_current_product",
    "get_product_name",
    "get_product_template_path",
    "Product",
    "ProductName",
    "setup_products",
)
