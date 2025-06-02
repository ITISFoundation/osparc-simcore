import logging

from aiohttp import web
from servicelib.mimetype_constants import MIMETYPE_TEXT_HTML

from ..products import products_web
from ._constants import (
    APP_FRONTEND_CACHED_INDEXES_KEY,
    APP_FRONTEND_CACHED_STATICS_JSON_KEY,
    FRONTEND_APPS_AVAILABLE,
)

_logger = logging.getLogger(__name__)


async def get_cached_frontend_index(request: web.Request):
    product_name = products_web.get_product_name(request)

    assert (  # nosec
        product_name in FRONTEND_APPS_AVAILABLE
    ), "Every product is mapped with a front-end app with IDENTICAL name"

    # NOTE: CANNOT redirect , i.e. `web.HTTPFound(f"/{target_frontend}/index.html")`
    # because it losses fragments and therefore it fails in study links.
    #
    # SEE services/web/server/tests/unit/isolated/test_redirections.py
    #

    cached_index_per_product: dict[str, str] = request.app[
        APP_FRONTEND_CACHED_INDEXES_KEY
    ]
    if product_name not in cached_index_per_product:
        raise web.HTTPNotFound(text=f"No index.html found for {product_name}")

    return web.Response(
        body=cached_index_per_product[product_name], content_type=MIMETYPE_TEXT_HTML
    )


async def get_statics_json(request: web.Request):
    product_name = products_web.get_product_name(request)

    return web.Response(
        body=request.app[APP_FRONTEND_CACHED_STATICS_JSON_KEY].get(product_name, None),
        content_type="application/json",
    )
