import logging

from aiohttp import web
from servicelib.statics_constants import (
    APP_FRONTEND_CACHED_INDEXES_KEY,
    APP_FRONTEND_CACHED_STATICS_JSON_KEY,
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
)

from ._constants import RQ_PRODUCT_FRONTEND_KEY, RQ_PRODUCT_KEY
from .products import get_product_name

log = logging.getLogger(__name__)


async def get_cached_frontend_index(request: web.Request):
    log.debug("Request from host %s", request.headers["Host"])
    target_frontend = request.get(RQ_PRODUCT_FRONTEND_KEY)

    if target_frontend is None:
        log.warning("No front-end specified using default %s", FRONTEND_APP_DEFAULT)
        target_frontend = FRONTEND_APP_DEFAULT

    elif target_frontend not in FRONTEND_APPS_AVAILABLE:
        raise web.HTTPNotFound(
            reason=f"Requested front-end '{target_frontend}' is not available"
        )

    log.debug(
        "Serving front-end %s for product %s",
        request.get(RQ_PRODUCT_KEY),
        target_frontend,
    )

    # NOTE: CANNOT redirect , i.e.
    # raise web.HTTPFound(f"/{target_frontend}/index.html")
    # because it losses fragments and therefore it fails in study links.
    #
    # SEE services/web/server/tests/unit/isolated/test_redirections.py
    #

    cached_indexes: dict[str, str] = request.app[APP_FRONTEND_CACHED_INDEXES_KEY]
    if target_frontend not in cached_indexes:
        raise web.HTTPNotFound()

    body = cached_indexes[target_frontend]
    return web.Response(body=body, content_type="text/html")


async def get_statics_json(request: web.Request):
    product_name = get_product_name(request)

    statics_json = request.app[APP_FRONTEND_CACHED_STATICS_JSON_KEY].get(
        product_name, {}
    )
    return web.Response(body=statics_json, content_type="application/json")
