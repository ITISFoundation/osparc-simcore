import logging
from typing import Optional, Pattern, List

import sqlalchemy as sa
from aiohttp import web

from pydantic import BaseModel, ValidationError, validator
from servicelib.application_setup import ModuleCategory, app_module_setup

from .__version__ import api_vtag
from .constants import APP_DB_ENGINE_KEY, APP_PRODUCTS_KEY, RQ_PRODUCT_KEY, RQ_PRODUCT_FRONTEND_KEY
from .db_models import products
from .statics import FRONTEND_APPS_AVAILABLE
from aiopg.sa.engine import Engine

log = logging.getLogger(__name__)


class Product(BaseModel):
    # pylint:disable=no-self-use
    # pylint:disable=no-self-argument
    name: str
    host_regex: Pattern

    @validator("name", pre=True, always=True)
    def validate_name(cls, v):
        if v not in FRONTEND_APPS_AVAILABLE:
            raise ValueError(
                f"{v} is not in available front-end apps {FRONTEND_APPS_AVAILABLE}"
            )
        return v


async def load_products_from_db(app: web.Application):
    # load from database defined products and map with front-end??
    app_products = []
    engine: Engine = app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        stmt = sa.select([products.c.name, products.c.host_regex])
        async for row in conn.execute(stmt):
            try:
                app_products.append(Product(name=row[0], host_regex=row[1]))
            except ValidationError as err:
                log.error("Discarding invalid product in db %s: %s", row, err)

    app[APP_PRODUCTS_KEY] = app_products


def discover_product_by_hostname(request: web.Request) -> Optional[str]:
    app_products: List[Product] = request.app[APP_PRODUCTS_KEY]
    for product in app_products:
        if product.host_regex.search(request.host):
            return product.name
    return None


@web.middleware
async def discover_product_middleware(request, handler):
    # NOTE: RQ_PRODUCT_KEY entry is ONLY for root or API entrypoints
    # NOTE: RQ_PRODUCT_KEY can return None
    #
    if request.path == "/": # root
        product_name: Optional[str] = discover_product_by_hostname(request)
        request[RQ_PRODUCT_FRONTEND_KEY] = request[RQ_PRODUCT_KEY] = product_name

    if request.path.startswith(f"/{api_vtag}"): # API entrypoints
        product_name: Optional[str] = discover_product_by_hostname(request)
        request[RQ_PRODUCT_KEY] = product_name

    response = await handler(request)

    return response


@app_module_setup(
    __name__, ModuleCategory.ADDON, depends=["simcore_service_webserver.db"], logger=log
)
def setup_products(app: web.Application):

    app.middlewares.append(discover_product_middleware)
    app.on_startup.append(load_products_from_db)
