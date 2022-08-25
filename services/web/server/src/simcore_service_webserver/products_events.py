import logging

from aiohttp import web
from aiopg.sa.engine import Engine
from pydantic import ValidationError

from ._constants import APP_DB_ENGINE_KEY, APP_PRODUCTS_KEY
from .products_db import Product, iter_products
from .statics_constants import FRONTEND_APP_DEFAULT, FRONTEND_APPS_AVAILABLE

log = logging.getLogger(__name__)


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
            log.error(
                "Invalid product in db '%s'. Skipping product info:\n %s", row, err
            )

    if FRONTEND_APP_DEFAULT not in app_products.keys():
        log.warning("Default front-end app is not in the products table")

    app[APP_PRODUCTS_KEY] = app_products
