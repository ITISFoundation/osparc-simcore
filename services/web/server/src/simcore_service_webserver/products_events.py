import logging
import tempfile
from pathlib import Path

from aiohttp import web
from aiopg.sa.engine import Engine
from pydantic import ValidationError
from servicelib.exceptions import InvalidConfig

from ._constants import APP_DB_ENGINE_KEY, APP_PRODUCTS_KEY
from .products_db import iter_products
from .products_model import Product
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


def _set_app_state(app: web.Application, app_products: dict[str, Product]):
    app[APP_PRODUCTS_KEY] = app_products
    # default is the first of a sorted priority-based list
    app[f"{APP_PRODUCTS_KEY}_default"] = next(iter(app_products.values())).name


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

            assert name in FRONTEND_APPS_AVAILABLE  # nosec

        except ValidationError as err:
            raise InvalidConfig(
                f"Invalid product configuration in db '{row}':\n {err}"
            ) from err

    assert FRONTEND_APP_DEFAULT in app_products.keys()  # nosec

    _set_app_state(app, app_products)

    log.debug("Product loaded: %s", [p.name for p in app_products.values()])
