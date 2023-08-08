import logging

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

from .._constants import APP_PRODUCTS_KEY, RQ_PRODUCT_KEY, X_PRODUCT_NAME_HEADER
from .._meta import API_VTAG
from ._model import Product

log = logging.getLogger(__name__)


def discover_product_by_hostname(request: web.Request) -> str | None:
    products: dict[str, Product] = request.app[APP_PRODUCTS_KEY]
    for product in products.values():
        if product.host_regex.search(request.host):
            product_name: str = product.name
            return product_name
    return None


def discover_product_by_request_header(request: web.Request) -> str | None:
    requested_product: str | None = request.headers.get(X_PRODUCT_NAME_HEADER)
    if requested_product:
        for product_name in request.app[APP_PRODUCTS_KEY]:
            if requested_product == product_name:
                return requested_product
    return None


def _get_app_default_product_name(request: web.Request) -> str:
    product_name: str = request.app[f"{APP_PRODUCTS_KEY}_default"]
    return product_name


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
            or _get_app_default_product_name(request)
        )
        request[RQ_PRODUCT_KEY] = product_name

    # - Publications entrypoint: redirections from other websites. SEE studies_access.py::access_study
    # - Root entrypoint: to serve front-end apps
    elif (
        request.path.startswith("/study/")
        or request.path.startswith("/view")
        or request.path == "/"
    ):
        product_name = discover_product_by_hostname(
            request
        ) or _get_app_default_product_name(request)

        request[RQ_PRODUCT_KEY] = product_name

    return await handler(request)
