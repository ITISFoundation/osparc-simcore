import logging
import textwrap

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER

from .._meta import API_VTAG
from ..constants import RQ_PRODUCT_KEY
from ..utils_aiohttp import iter_origins
from ._application_keys import DEFAULT_PRODUCT_APPKEY, PRODUCTS_APPKEY

_logger = logging.getLogger(__name__)


def _get_default_product_name(app: web.Application) -> str:
    product_name: str = app[DEFAULT_PRODUCT_APPKEY]
    return product_name


def _discover_product_by_hostname(request: web.Request) -> str | None:
    products = request.app[PRODUCTS_APPKEY]
    for product in products.values():
        for _, host in iter_origins(request):
            if product.host_regex.search(host):
                product_name: str = product.name
                return product_name
    return None


def _discover_product_by_request_header(request: web.Request) -> str | None:
    requested_product: str | None = request.headers.get(X_PRODUCT_NAME_HEADER)
    if requested_product:
        for product_name in request.app[PRODUCTS_APPKEY]:
            if requested_product == product_name:
                return requested_product
    return None


def _get_debug_msg(request: web.Request):
    return "\n".join(
        [
            f"{request.url=}",
            f"{request.host=}",
            f"{request.remote=}",
            *[f"{k}:{request.headers[k][:20]}" for k in request.headers],
            f"{request.headers.get('X-Forwarded-Host')=}",
            f"{request.get(RQ_PRODUCT_KEY)=}",
        ]
    )


@web.middleware
async def discover_product_middleware(request: web.Request, handler: Handler):
    """
    This service can serve to different products
    Every request needs to reveal which product to serve and store it in request[RQ_PRODUCT_KEY]
        - request[RQ_PRODUCT_KEY] is set to discovered product in 3 types of entrypoints
        - if no product discovered, then it is set to default
    """

    if (
        # - API entrypoints
        # - /static info for front-end
        # - socket-io
        request.path.startswith(f"/{API_VTAG}")
        or request.path in {"/static-frontend-data.json", "/socket.io/"}
    ):
        request[RQ_PRODUCT_KEY] = (
            _discover_product_by_request_header(request)
            or _discover_product_by_hostname(request)
            or _get_default_product_name(request.app)
        )

    else:
        # - Publications entrypoint: redirections from other websites. SEE studies_access.py::access_study
        # - Root entrypoint: to serve front-end apps
        assert (  # nosec
            request.path.startswith("/dev/")
            or request.path.startswith("/study/")
            or request.path.startswith("/view")
            or request.path == "/"
        )
        request[RQ_PRODUCT_KEY] = _discover_product_by_hostname(
            request
        ) or _get_default_product_name(request.app)

    _logger.debug(
        "Product middleware result: \n%s\n",
        textwrap.indent(_get_debug_msg(request), " "),
    )
    assert request[RQ_PRODUCT_KEY]  # nosec

    return await handler(request)
