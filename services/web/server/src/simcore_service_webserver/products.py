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
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._constants import APP_PRODUCTS_KEY, APP_SETTINGS_KEY, RQ_PRODUCT_KEY
from ._resources import resources
from .products_db import ProductRepository
from .products_events import (
    APP_PRODUCTS_TEMPLATES_DIR_KEY,
    auto_create_products_groups,
    load_products_on_startup,
    setup_product_templates,
)
from .products_middlewares import discover_product_middleware
from .products_model import Product

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
    return request[RQ_PRODUCT_KEY]


def get_current_product(request: web.Request) -> Product:
    """Returns product associated to current request"""
    product_name = get_product_name(request)
    return request.app[APP_PRODUCTS_KEY][product_name]


def list_products(app: web.Application) -> list[Product]:
    return app[APP_PRODUCTS_KEY].values()


async def get_product_template_path(request: web.Request, filename: str) -> Path:
    def _themed(dirname, template) -> Path:
        return resources.get_path(os.path.join(dirname, template))

    try:
        product: Product = get_current_product(request)

        if template_name := product.get_template_name_for(filename):
            template_dir = request.app[APP_PRODUCTS_TEMPLATES_DIR_KEY]
            template_path = template_dir / template_name
            if not template_path.exists():
                # cached
                try:
                    repo = ProductRepository(request)
                    async with aiofiles.open(template_path, "wt") as fh:
                        await fh.write(await repo.get_template_content(template_name))
                except Exception:
                    if template_path.exists():
                        template_path.unlink()
                    raise

            return template_path

        # check static resources
        if (
            template_path := _themed(f"templates/{product.name}", filename)
        ) and template_path.exists():
            return template_path

    except KeyError:
        # undefined product
        pass

    default_template = _themed("templates/common", filename)
    if not default_template.exists():
        raise ValueError(f"{filename} is not part of the templates/common")

    return default_template


__all__: tuple[str, ...] = (
    "get_current_product",
    "get_product_name",
    "Product",
    "setup_products",
    "get_product_template_path",
)
