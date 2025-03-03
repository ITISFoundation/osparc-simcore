import logging
import tempfile
from pathlib import Path

from aiohttp import web
from models_library.products import ProductName
from simcore_postgres_database.utils_products import (
    get_or_create_product_group,
)

from ..constants import APP_PRODUCTS_KEY
from ..db.plugin import get_database_engine
from . import _service
from ._repository import iter_products
from .models import Product

_logger = logging.getLogger(__name__)

APP_PRODUCTS_TEMPLATES_DIR_KEY = f"{__name__}.template_dir"


async def setup_product_templates(app: web.Application):
    """
    builds a directory and download product templates
    """
    with tempfile.TemporaryDirectory(
        suffix=APP_PRODUCTS_TEMPLATES_DIR_KEY
    ) as templates_dir:
        app[APP_PRODUCTS_TEMPLATES_DIR_KEY] = Path(templates_dir)

        yield

        # cleanup


async def auto_create_products_groups(app: web.Application) -> None:
    """Ensures all products have associated group ids

    Avoids having undefined groups in products with new products.group_id column

    NOTE: could not add this in 'setup_groups' (groups plugin)
    since it has to be executed BEFORE 'load_products_on_startup'
    """
    engine = get_database_engine(app)

    async with engine.acquire() as connection:
        async for row in iter_products(connection):
            product_name = row.name  # type: ignore[attr-defined] # sqlalchemy
            product_group_id = await get_or_create_product_group(
                connection, product_name
            )
            _logger.debug(
                "Product with %s has an associated group with %s",
                f"{product_name=}",
                f"{product_group_id=}",
            )


def _set_app_state(
    app: web.Application,
    app_products: dict[ProductName, Product],
    default_product_name: str,
):
    app[APP_PRODUCTS_KEY] = app_products
    assert default_product_name in app_products  # nosec
    app[f"{APP_PRODUCTS_KEY}_default"] = default_product_name


async def load_products_on_startup(app: web.Application):
    """
    Loads info on products stored in the database into app's storage (i.e. memory)
    """
    app_products: dict[ProductName, Product] = {
        product.name: product for product in await _service.load_products(app)
    }

    default_product_name = await _service.get_default_product_name(app)

    _set_app_state(app, app_products, default_product_name)

    _logger.debug("Product loaded: %s", list(app_products))
