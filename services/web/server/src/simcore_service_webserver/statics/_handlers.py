import logging

from aiohttp import web

from ..products.api import get_product_name
from ._constants import (
    APP_FRONTEND_CACHED_INDEXES_KEY,
    APP_FRONTEND_CACHED_STATICS_JSON_KEY,
    FRONTEND_APPS_AVAILABLE,
)

_logger = logging.getLogger(__name__)


async def get_cached_frontend_index(request: web.Request):
    product_name = get_product_name(request)

    assert (  # nosec
        product_name in FRONTEND_APPS_AVAILABLE
    ), "Every product is mapped with a front-end app with IDENTICAL name"

    # NOTE: CANNOT redirect , i.e.
    # raise web.HTTPFound(f"/{target_frontend}/index.html")
    # because it losses fragments and therefore it fails in study links.
    #
    # SEE services/web/server/tests/unit/isolated/test_redirections.py
    #

    cached_index_per_product: dict[str, str] = request.app[
        APP_FRONTEND_CACHED_INDEXES_KEY
    ]
    if product_name not in cached_index_per_product:
        raise web.HTTPNotFound(reason=f"No index.html found for {product_name}")

    return web.Response(
        body=cached_index_per_product[product_name], content_type="text/html"
    )


async def get_statics_json(request: web.Request):
    product_name = get_product_name(request)

    statics_json = request.app[APP_FRONTEND_CACHED_STATICS_JSON_KEY].get(
        product_name, {}
    )
    return web.Response(body=statics_json, content_type="application/json")
