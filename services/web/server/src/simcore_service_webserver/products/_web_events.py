import logging
import tempfile
from pathlib import Path
from pprint import pformat
from typing import Final

from aiohttp import web
from models_library.products import ProductName

from . import _service
from ._application_keys import DEFAULT_PRODUCT_APPKEY, PRODUCTS_APPKEY
from ._models import Product

_logger = logging.getLogger(__name__)

PRODUCTS_TEMPLATES_DIR_APPKEY: Final = web.AppKey("PRODUCTS_TEMPLATES_DIR", Path)


async def _auto_create_products_groups(app: web.Application) -> None:
    """Ensures all products have associated group ids

    Avoids having undefined groups in products with new products.group_id column

    NOTE: could not add this in 'setup_groups' (groups plugin)
    since it has to be executed BEFORE 'load_products_on_startup'
    """
    product_groups_map = await _service.auto_create_products_groups(app)
    _logger.debug("Products group IDs: %s", pformat(product_groups_map))


def _set_app_state(
    app: web.Application,
    app_products: dict[ProductName, Product],
    default_product_name: str,
):
    # NOTE: products are checked on every request, therefore we
    # cache them in the `app` upon startup
    app[PRODUCTS_APPKEY] = app_products
    assert default_product_name in app_products  # nosec
    app[DEFAULT_PRODUCT_APPKEY] = default_product_name


async def _load_products_on_startup(app: web.Application):
    """
    Loads info on products stored in the database into app's storage (i.e. memory)
    """
    app_products: dict[ProductName, Product] = {
        product.name: product for product in await _service.load_products(app)
    }

    default_product_name = await _service.get_default_product_name(app)

    _set_app_state(app, app_products, default_product_name)
    assert PRODUCTS_APPKEY in app  # nosec

    _logger.debug("Product loaded: %s", list(app_products))


async def _setup_product_templates(app: web.Application):
    """
    builds a directory and download product templates
    """
    with tempfile.TemporaryDirectory(suffix="product_template_") as templates_dir:
        app[PRODUCTS_TEMPLATES_DIR_APPKEY] = Path(templates_dir)

        yield

        # cleanup


def setup_web_events(app: web.Application):
    app.on_startup.append(
        # NOTE: must go BEFORE _load_products_on_startup
        _auto_create_products_groups
    )
    app.on_startup.append(_load_products_on_startup)
    app.cleanup_ctx.append(_setup_product_templates)
