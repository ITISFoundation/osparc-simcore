import logging
import tempfile
from pathlib import Path

from aiohttp import web
from aiopg.sa.engine import Engine
from pydantic import ValidationError
from servicelib.exceptions import InvalidConfig

from ._constants import APP_DB_ENGINE_KEY, APP_PRODUCTS_KEY
from .products_db import Product, iter_products
from .statics_constants import FRONTEND_APP_DEFAULT, FRONTEND_APPS_AVAILABLE

log = logging.getLogger(__name__)

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


async def load_products_on_startup(app: web.Application):
    """
    Loads info on products stored in the database into app's storage (i.e. memory)
    """
    app_products: dict[str, Product] = {}
    engine: Engine = app[APP_DB_ENGINE_KEY]

    async for row in iter_products(engine):
        try:
            name = row.name  # type:ignore
            app_products[name] = Product.from_orm(row)

            if name not in FRONTEND_APPS_AVAILABLE:
                log.warning("There is not front-end registered for this product")

        except ValidationError as err:
            raise InvalidConfig(
                f"Invalid product configuration in db '{row}':\n {err}"
            ) from err

    if FRONTEND_APP_DEFAULT not in app_products.keys():
        log.warning("Default front-end app is not in the products table")

    app[APP_PRODUCTS_KEY] = app_products
    log.debug("Product loaded: %s", [p.name for p in app_products.values()])
