import logging
from typing import Optional

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

from ._constants import (
    APP_PRODUCTS_KEY,
    RQ_PRODUCT_FRONTEND_KEY,
    RQ_PRODUCT_KEY,
    X_PRODUCT_NAME_HEADER,
)
from ._meta import API_VTAG
from .statics_constants import FRONTEND_APP_DEFAULT

log = logging.getLogger(__name__)


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


@web.middleware
async def discover_product_middleware(request: web.Request, handler: Handler):
    """
    This service can serve to different products
    Every request needs to reveal which product to serve and store it in request[RQ_PRODUCT_KEY]
        - request[RQ_PRODUCT_KEY] is set to discovered product in 3 types of entrypoints
        - if no product discovered, then it is set to default
    """
    # - API entrypoints
    # - /static info for front-end
    if (
        request.path.startswith(f"/{API_VTAG}")
        or request.path == "/static-frontend-data.json"
    ):
        product_name = (
            discover_product_by_request_header(request)
            or discover_product_by_hostname(request)
            or FRONTEND_APP_DEFAULT
        )
        request[RQ_PRODUCT_KEY] = product_name

    # - Publications entrypoint: redirections from other websites. SEE studies_access.py::access_study
    # - Root entrypoint: to serve front-end apps
    elif (
        request.path.startswith("/study/")
        or request.path.startswith("/view")
        or request.path == "/"
    ):
        product_name = discover_product_by_hostname(request) or FRONTEND_APP_DEFAULT
        request[RQ_PRODUCT_FRONTEND_KEY] = request[RQ_PRODUCT_KEY] = product_name

    response = await handler(request)

    return response
