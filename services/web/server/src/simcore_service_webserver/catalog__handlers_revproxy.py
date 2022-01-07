import logging
from typing import Optional

from aiohttp import web

from . import catalog_client
from .catalog_client import to_backend_service
from .catalog_config import KCATALOG_ORIGIN, KCATALOG_VERSION_PREFIX
from .constants import RQ_PRODUCT_KEY, X_PRODUCT_NAME_HEADER
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required

logger = logging.getLogger(__name__)


@login_required
@permission_required("services.catalog.*")
async def reverse_proxy_handler(request: web.Request) -> web.Response:
    """
        - Adds auth layer
        - Adds access layer
        - Forwards request to catalog service

    SEE https://gist.github.com/barrachri/32f865c4705f27e75d3b8530180589fb
    """
    user_id = request[RQT_USERID_KEY]

    # path & queries
    backend_url = to_backend_service(
        request.rel_url,
        request.app[KCATALOG_ORIGIN],
        request.app[KCATALOG_VERSION_PREFIX],
    )
    # FIXME: hack
    if "/services" in backend_url.path:
        backend_url = backend_url.update_query({"user_id": user_id})
    logger.debug("Redirecting '%s' -> '%s'", request.url, backend_url)

    # body
    raw: Optional[bytes] = None
    if request.can_read_body:
        raw = await request.read()

    # injects product discovered by middleware in headers
    fwd_headers = request.headers.copy()
    product_name = request[RQ_PRODUCT_KEY]
    fwd_headers.update({X_PRODUCT_NAME_HEADER: product_name})

    # forward request
    return await catalog_client.make_request_and_envelope_response(
        request.app, request.method, backend_url, fwd_headers, raw
    )
