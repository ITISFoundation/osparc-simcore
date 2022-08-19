"""
This framework can serve different variants of the front-end client denoted 'products'

A product can be customized using settings defined in the backend (see products pg table).
Some of these are also transmitted to the front-end client via statics (see statis_settings.py)

At every request to this service API, a middleware discovers which product is the requester and sets the appropriate product context

"""


import logging
from typing import Optional, Pattern

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from pydantic import BaseModel, Field, HttpUrl, ValidationError, validator
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
    """
    Pydantic model associated to db_models.Products table

    The standard case is serving a single product, therefore defaults are set
    from env-vars.
    """

    name: str = Field(regex=PUBLIC_VARIABLE_NAME_RE)
    display_name: str
    host_regex: Pattern
    support_email: str
    twilio_messaging_sid: Optional[str] = Field(
        default=None,
        min_length=34,
        max_length=34,
    )
    manual_url: HttpUrl
    manual_extra_url: Optional[HttpUrl]
    issues_new_url: HttpUrl

    class Config:
        orm_mode = True

    @validator("name", pre=True, always=True)
    @classmethod
    def validate_name(cls, v):
        if v not in FRONTEND_APPS_AVAILABLE:
            raise ValueError(
                f"{v} is not in available front-end apps {FRONTEND_APPS_AVAILABLE}"
            )
        return v


async def load_products_from_db(app: web.Application):
    """
    Loads info on products stored in the database into app's storage (i.e. memory)
    """
    app_products: dict[str, Product] = {}
    engine: Engine = app[APP_DB_ENGINE_KEY]
    exclude = {products.c.created, products.c.modified}

    async with engine.acquire() as conn:
        stmt = sa.select([c for c in products.columns if c not in exclude])
        async for row in conn.execute(stmt):
            assert row  # nosec
            try:
                name = row.name  # type:ignore
                app_products[name] = Product.from_orm(row)
            except ValidationError as err:
                log.error("Discarding invalid product in db %s: %s", row, err)

    app[APP_PRODUCTS_KEY] = app_products


def discover_product_by_hostname(request: web.Request) -> Optional[str]:
    for product in request.app[APP_PRODUCTS_KEY].values():
        if product.host_regex.search(request.host):
            return product.name
    return None


def discover_product_by_request_header(request: web.Request) -> Optional[str]:
    requested_product = request.headers.get(X_PRODUCT_NAME_HEADER)
    if requested_product:
        for product_name in request.app[APP_PRODUCTS_KEY].keys():
            if requested_product == product_name:
                return requested_product
    return None


def get_product_context(request: web.Request) -> Product:
    product_name = request[RQ_PRODUCT_KEY]
    return request.app[APP_PRODUCTS_KEY][product_name]


@web.middleware
async def discover_product_middleware(request, handler):
    """
    This service can serve to different products
    Every request needs to reveal which product to serve and store it in request[RQ_PRODUCT_KEY]
        - request[RQ_PRODUCT_KEY] is set to discovered product in 3 types of entrypoints
        - if no product discovered, then it is set to default
    """
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
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.db"],
    settings_name="WEBSERVER_PRODUCTS",
    logger=log,
)
def setup_products(app: web.Application):

    assert app[APP_SETTINGS_KEY].WEBSERVER_PRODUCTS is True  # nosec

    app.middlewares.append(discover_product_middleware)
    app.on_startup.append(load_products_from_db)
