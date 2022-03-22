import logging
from typing import Optional

from aiohttp import web
from models_library.services import ServiceInput, ServiceOutput
from yarl import URL

from . import catalog_client
from ._constants import RQ_PRODUCT_KEY, X_PRODUCT_NAME_HEADER
from .catalog_client import to_backend_service
from .catalog_settings import get_plugin_settings
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
    settings = get_plugin_settings(request.app)

    # path & queries
    backend_url = to_backend_service(
        request.rel_url,
        URL(settings.base_url),
        settings.CATALOG_VTAG,
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


def can_connect(
    from_output: ServiceOutput, to_input: ServiceInput, *, strict: bool = False
) -> bool:
    # FIXME: can_connect is a very very draft version

    # compatible units
    ok = from_output.unit == to_input.unit
    if ok:
        # compatible types
        # FIXME: see mimetypes examples in property_type
        #
        #   "pattern": "^(number|integer|boolean|string|data:([^/\\s,]+/[^/\\s,]+|\\[[^/\\s,]+/[^/\\s,]+(,[^/\\s]+/[^/,\\s]+)*\\]))$",
        #   "description": "data type expected on this input glob matching for data type is allowed",
        #   "examples": [
        #     "number",
        #     "boolean",
        #     "data:*/*",
        #     "data:text/*",
        #     "data:[image/jpeg,image/png]",
        #     "data:application/json",
        #     "data:application/json;schema=https://my-schema/not/really/schema.json",
        #     "data:application/vnd.ms-excel",
        #     "data:text/plain",
        #     "data:application/hdf5",
        #     "data:application/edu.ucdavis@ceclancy.xyz"
        #
        ok = from_output.property_type == to_input.property_type
        if not ok:
            ok = (
                # data:  -> data:*/*
                to_input.property_type == "data:*/*"
                and from_output.property_type.startswith("data:")
            )

            if not strict:
                # NOTE: by default, this is allowed in the UI but not in a more strict plausibility check
                # data:*/*  -> data:
                ok |= (
                    from_output.property_type == "data:*/*"
                    and to_input.property_type.startswith("data:")
                )
    return ok
