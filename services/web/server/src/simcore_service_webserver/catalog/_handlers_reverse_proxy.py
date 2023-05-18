import logging

from aiohttp import web
from servicelib.logging_utils import get_log_record_extra
from yarl import URL

from .._constants import RQ_PRODUCT_KEY, RQT_USERID_KEY, X_PRODUCT_NAME_HEADER
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ._utils import make_request_and_envelope_response
from .client import to_backend_service
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


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
    settings = get_plugin_settings(request.app)

    # path & queries
    backend_url = to_backend_service(
        request.rel_url,
        URL(settings.base_url),
        settings.CATALOG_VTAG,
    )
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/4237
    if "/services" in backend_url.path:
        backend_url = backend_url.update_query({"user_id": user_id})

    _logger.debug(
        "Redirecting '%s' -> '%s'",
        request.url,
        backend_url,
        extra=get_log_record_extra(user_id=user_id),
    )

    # body
    raw: bytes | None = None
    if request.can_read_body:
        raw = await request.read()

    # injects product discovered by middleware in headers
    fwd_headers = request.headers.copy()
    product_name = request[RQ_PRODUCT_KEY]
    fwd_headers.update({X_PRODUCT_NAME_HEADER: product_name})

    # forward request
    return await make_request_and_envelope_response(
        request.app, request.method, backend_url, fwd_headers, raw
    )
