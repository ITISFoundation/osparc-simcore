import logging
from typing import Optional, Pattern

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from pydantic import BaseModel, ValidationError, validator
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._constants import (
    APP_DB_ENGINE_KEY,
    APP_PRODUCTS_KEY,
    APP_SETTINGS_KEY,
    RQ_PRODUCT_FRONTEND_KEY,
    RQ_PRODUCT_KEY,
    X_PRODUCT_NAME_HEADER,
)
from ._meta import API_VTAG
from .db_models import products
from .statics_constants import FRONTEND_APP_DEFAULT, FRONTEND_APPS_AVAILABLE

log = logging.getLogger(__name__)


class Product(BaseModel):
    name: str
    host_regex: Pattern

    @validator("name", pre=True, always=True)
    @classmethod
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
    for product in request.app[APP_PRODUCTS_KEY]:
        if product.host_regex.search(request.host):
            return product.name
    return None


def discover_product_by_request_header(request: web.Request) -> Optional[str]:
    requested_product = request.headers.get(X_PRODUCT_NAME_HEADER)
    if requested_product:
        for product in request.app[APP_PRODUCTS_KEY]:
            if requested_product == product.name:
                return requested_product
    return None


@web.middleware
async def discover_product_middleware(request, handler):
    #
    # - request[RQ_PRODUCT_KEY] is set to discovered product in 3 types of entrypoints
    # - if no product discovered, then it is set to default
    #

    # API entrypoints: api calls
    if request.path.startswith(f"/{API_VTAG}"):
        product_name = (
            discover_product_by_request_header(request)
            or discover_product_by_hostname(request)
            or FRONTEND_APP_DEFAULT
        )
        request[RQ_PRODUCT_KEY] = product_name

    # Publications entrypoint: redirections from other websites. SEE studies_access.py::access_study
    elif request.path.startswith("/study/"):
        product_name = discover_product_by_hostname(request) or FRONTEND_APP_DEFAULT
        request[RQ_PRODUCT_FRONTEND_KEY] = request[RQ_PRODUCT_KEY] = product_name

    # Root entrypoint: to serve front-end apps
    elif request.path == "/":
        product_name = discover_product_by_hostname(request) or FRONTEND_APP_DEFAULT
        request[RQ_PRODUCT_FRONTEND_KEY] = request[RQ_PRODUCT_KEY] = product_name

    response = await handler(request)

    return response


@app_module_setup(
    __name__, ModuleCategory.ADDON, depends=["simcore_service_webserver.db"], logger=log
)
def setup_products(app: web.Application):

    assert app[APP_SETTINGS_KEY].WEBSERVER_PRODUCTS is True  # nosec

    app.middlewares.append(discover_product_middleware)
    app.on_startup.append(load_products_from_db)
