import logging
import tempfile
from pathlib import Path

from aiohttp import web
from aiopg.sa.engine import Engine
from pydantic import ValidationError
from servicelib.exceptions import InvalidConfig
from simcore_postgres_database.utils_products import (
    get_default_product_name,
    get_or_create_product_group,
)
from simcore_postgres_database.utils_products_prices import is_payment_enabled

from .._constants import APP_DB_ENGINE_KEY, APP_PRODUCTS_KEY
from ..statics._constants import FRONTEND_APP_DEFAULT, FRONTEND_APPS_AVAILABLE
from ._db import iter_products
from ._model import Product

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
    engine: Engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as connection:
        async for row in iter_products(connection):
            product_name = row.name
            product_group_id = await get_or_create_product_group(
                connection, product_name
            )
            _logger.debug(
                "Product with %s has an associated group with %s",
                f"{product_name=}",
                f"{product_group_id=}",
            )


def _set_app_state(
    app: web.Application, app_products: dict[str, Product], default_product_name: str
):
    app[APP_PRODUCTS_KEY] = app_products
    assert default_product_name in app_products  # nosec
    app[f"{APP_PRODUCTS_KEY}_default"] = default_product_name


async def load_products_on_startup(app: web.Application):
    """
    Loads info on products stored in the database into app's storage (i.e. memory)
    """
    app_products: dict[str, Product] = {}
    engine: Engine = app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as connection:
        async for row in iter_products(connection):
            try:
                name = row.name
                is_enabled = await is_payment_enabled(connection, product_name=name)
                app_products[name] = Product(
                    **dict(row.items()), is_payment_enabled=is_enabled
                )

                assert name in FRONTEND_APPS_AVAILABLE  # nosec

            except ValidationError as err:  # noqa: PERF203
                msg = f"Invalid product configuration in db '{row}':\n {err}"
                raise InvalidConfig(msg) from err

        assert FRONTEND_APP_DEFAULT in app_products  # nosec

        default_product_name = await get_default_product_name(connection)

    _set_app_state(app, app_products, default_product_name)

    _logger.debug("Product loaded: %s", [p.name for p in app_products.values()])
