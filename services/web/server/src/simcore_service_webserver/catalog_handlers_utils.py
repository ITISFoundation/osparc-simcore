import logging
from typing import Optional

from aiohttp import web
from models_library.services import BaseServiceIOModel, ServiceInput, ServiceOutput
from pint import PintError, UnitRegistry
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


## PORT COMPATIBILITY ---------------------------------


def _get_unit(port: BaseServiceIOModel) -> str:
    unit = port.unit
    if port.property_type == "ref_contentSchema":
        if port.content_schema["type"] in ("object", "array"):
            raise NotImplementedError
        unit = port.content_schema.get("x-unit", unit)
    return unit


def _get_type(port: BaseServiceIOModel) -> str:
    _type = port.property_type
    if port.property_type == "ref_contentSchema":
        _type = port.content_schema["type"]
    return _type


def _can_convert_units(
    from_unit: Optional[str], to_unit: Optional[str], ureg: UnitRegistry
) -> bool:
    try:
        return ureg.Quantity(from_unit).check(to_unit)
    except (TypeError, PintError):
        return False


def can_connect(
    from_output: ServiceOutput,
    to_input: ServiceInput,
    *,
    units_registry: UnitRegistry,
    strict: bool = False,
) -> bool:

    ResultIfUndefined = False if strict else True

    # types check
    from_type = _get_type(from_output)
    to_type = _get_type(to_input)

    if any(t in ("object", "array") for t in (from_type, to_type)):
        return ResultIfUndefined

    ok = from_type == to_type
    if not ok:
        ok = (
            # data:  -> data:*/*
            to_type == "data:*/*"
            and from_type.startswith("data:")
        )

        if not strict:
            # NOTE: by default, this is allowed in the UI but not in a more strict plausibility check
            # data:*/*  -> data:
            ok |= from_output.property_type == "data:*/*" and to_type.startswith(
                "data:"
            )

    # units check
    if ok:
        try:
            from_unit = _get_unit(from_output)
            to_unit = _get_unit(to_input)
        except NotImplementedError:
            return ResultIfUndefined

        if strict:
            ok = (from_unit is None and to_unit is None) or _can_convert_units(
                from_unit, to_unit, units_registry
            )
        else:
            ok = (
                from_unit is None
                or to_unit is None
                or _can_convert_units(from_unit, to_unit, units_registry)
            )

    return ok
