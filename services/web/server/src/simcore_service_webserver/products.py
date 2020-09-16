import logging
import re
from typing import AnyStr,  Optional, Pattern, List

import sqlalchemy as sa
from aiohttp import web

from pydantic import BaseModel, ValidationError, validator
from servicelib.application_setup import ModuleCategory, app_module_setup

from .__version__ import api_vtag
from .constants import APP_DB_ENGINE_KEY, APP_PRODUCTS_KEY, RQ_PRODUCT_KEY
from .db_models import products
from .statics import FRONTEND_APPS_AVAILABLE

log = logging.getLogger(__name__)


class Product(BaseModel):
    # pylint:disable=no-self-use
    # pylint:disable=no-self-argument

    name: str
    host_regex: Pattern
    frontend: Optional[str]


    @validator("frontend", pre=True, always=True)
    def default_frontend(cls, v, *, values):
        if v is None:
            return values["name"]

        if v not in FRONTEND_APPS_AVAILABLE:
            raise ValueError(
                f"{v} is not in available front-end apps {FRONTEND_APPS_AVAILABLE}"
            )
        return v


async def load_products_from_db(app: web.Application):
    # load from database defined products and map with front-end??
    app_products = []

    with app[APP_DB_ENGINE_KEY].acquire() as conn:
        stmt = sa.select([products.c.name, products.c.host_regex, products.c.frontend])
        async for row in conn.execute(stmt):
            try:
                app_products.append(Product(*row))
            except ValidationError as err:
                log.error("Invalid db row %s: %s . Discarding", row, err)

    app[APP_PRODUCTS_KEY] = app_products


def discover_product_by_hostname(request: web.Request) -> Optional[str]:
    app_products: List[Product] = request.app[APP_PRODUCTS_KEY]
    for product in app_products:
        if product.host_regex.search(request.host):
            return product.name


@web.middleware
async def discover_product_middleware(request, handler):
    # NOTE: RQ_PRODUCT_KEY entry is ONLY for root or API entrypoints
    # NOTE: RQ_PRODUCT_KEY can return None
    if request.path == "/" or request.path.startswith(f"/{api_vtag}"):
        product_name: Optional[str] = discover_product_by_hostname(request)
        request[RQ_PRODUCT_KEY] = product_name

    response = await handler(request)

    return response


@app_module_setup(
    __name__, ModuleCategory.ADDON, depends=["simcore_service_webserver.db"], logger=log
)
def setup_products(app: web.Application):

    app.middlewares.append(discover_product_middleware)
    app.on_startup(load_products_from_db)
