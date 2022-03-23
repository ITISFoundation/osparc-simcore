import logging
from dataclasses import dataclass
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


##  MODELS UTILS ---------------------------------


def _get_unit_name(port: BaseServiceIOModel) -> str:
    unit = port.unit
    if port.property_type == "ref_contentSchema":
        if port.content_schema["type"] in ("object", "array"):
            raise NotImplementedError
        unit = port.content_schema.get("x_unit", unit)
        if unit:
            # FIXME: x_units has a special format for prefix. tmp direct replace here
            unit = unit.replace("-", "")
    return unit


def _get_type_name(port: BaseServiceIOModel) -> str:
    _type = port.property_type
    if port.property_type == "ref_contentSchema":
        _type = port.content_schema["type"]
    return _type


@dataclass
class UnitHtmlFormat:
    short: str
    long: str


def get_html_formatted_unit(
    port: BaseServiceIOModel, ureg: UnitRegistry
) -> Optional[UnitHtmlFormat]:
    try:
        unit_name = _get_unit_name(port)
        if unit_name is None:
            return None

        q = ureg.Quantity(unit_name)
        return UnitHtmlFormat(short=f"{q.units:~H}", long=f"{q.units:H}")
    except PintError:
        return None


## PORT COMPATIBILITY ---------------------------------


def _can_convert_units(from_unit: str, to_unit: str, ureg: UnitRegistry) -> bool:
    assert from_unit  # nosec
    assert to_unit  # nosec

    # TODO: optimize by caching?  ureg already caches?
    # TODO: symmetric
    try:
        return ureg.Quantity(from_unit).check(to_unit)
    except (TypeError, PintError):
        return False


def can_connect(
    from_output: ServiceOutput,
    to_input: ServiceInput,
    units_registry: UnitRegistry,
) -> bool:
    """Checks compatibility between ports.

    This check IS PERMISSIVE and is used for checks in the UI where one needs to give some "flexibility" since:
    - has to be a fast evaluation
    - there are not error messages when check fails
    - some configurations might need several UI steps to be valid

    For more strict checks use the "strict" variant
    """
    # types check
    from_type = _get_type_name(from_output)
    to_type = _get_type_name(to_input)

    ok = (
        from_type == to_type
        or (
            # data:  -> data:*/*
            to_type == "data:*/*"
            and from_type.startswith("data:")
        )
        or (
            # NOTE: by default, this is allowed in the UI but not in a more strict plausibility check
            # data:*/*  -> data:
            from_type == "data:*/*"
            and to_type.startswith("data:")
        )
    )

    if any(t in ("object", "array") for t in (from_type, to_type)):
        # Not Implemented but this if e.g. from_type == to_type that should be the answer
        # TODO: from_type subset of to_type is the right way resolve this check
        return ok

    # types units
    if ok:
        try:
            from_unit = _get_unit_name(from_output)
            to_unit = _get_unit_name(to_input)
        except NotImplementedError:
            return ok

        ok = ok and (
            from_unit == to_unit
            # unitless -> *
            or from_unit is None
            # * -> unitless
            or to_unit is None
            # from_unit -> unit
            or _can_convert_units(from_unit, to_unit, units_registry)
        )

    return ok


def check_connect_strict(
    from_output: ServiceOutput,
    to_input: ServiceInput,
    units_registry: UnitRegistry,
):
    raise NotImplementedError("Strict ports compatibility check still not implemented")
