import logging
import os
from dataclasses import dataclass
from typing import Any, Final

import cachetools
from models_library.api_schemas_webserver.catalog import (
    ServiceInputGet,
    ServiceInputKey,
    ServiceOutputGet,
    ServiceOutputKey,
)
from models_library.services import BaseServiceIOModel
from pint import PintError, UnitRegistry

_logger = logging.getLogger(__name__)


def get_unit_name(port: BaseServiceIOModel) -> str | None:
    unit: str | None = port.unit
    if port.property_type == "ref_contentSchema":
        assert port.content_schema is not None  # nosec
        # NOTE: content schema might not be resolved (i.e. has $ref!! )
        unit = port.content_schema.get("x_unit", unit)
        if unit:
            # WARNING: has a special format for prefix. tmp direct replace here
            unit = unit.replace("-", "")
        elif port.content_schema.get("type") in ("object", "array", None):
            # these objects might have unit in its fields
            raise NotImplementedError
    return unit


@dataclass
class UnitHtmlFormat:
    short: str
    long: str


def get_html_formatted_unit(
    port: BaseServiceIOModel, ureg: UnitRegistry
) -> UnitHtmlFormat | None:
    try:
        unit_name = get_unit_name(port)
        if unit_name is None:
            return None

        q = ureg.Quantity(unit_name)
        return UnitHtmlFormat(short=f"{q.units:~H}", long=f"{q.units:H}")
    except (PintError, NotImplementedError):
        return None


#
# Transforms from catalog api models -> webserver api models
#


# Caching:  https://cachetools.readthedocs.io/en/latest/index.html#cachetools.TTLCache
# - the least recently used items will be discarded first to make space when necessary.
#

_CACHE_MAXSIZE: Final = int(
    os.getenv("CACHETOOLS_CACHE_MAXSIZE", "100")
)  # number of items  i.e. ServiceInputGet/ServiceOutputGet instances
_CACHE_TTL: Final = int(os.getenv("CACHETOOLS_CACHE_TTL_SECS", "60"))  # secs


def _hash_inputs(
    service: dict[str, Any],
    input_key: str,
    *args,  # noqa: ARG001 # pylint: disable=unused-argument
    **kwargs,  # noqa: ARG001 # pylint: disable=unused-argument
):
    return f"{service['key']}/{service['version']}/{input_key}"


def _cachetools_cached(*args, **kwargs):
    def decorator(func):
        if os.getenv("CACHETOOLS_DISABLE", "0") == "0":
            return cachetools.cached(*args, **kwargs)(func)
        _logger.warning("cachetools disabled")
        return func

    return decorator


class ServiceInputGetFactory:
    @staticmethod
    @_cachetools_cached(
        cachetools.TTLCache(ttl=_CACHE_TTL, maxsize=_CACHE_MAXSIZE), key=_hash_inputs
    )
    def from_catalog_service_api_model(
        service: dict[str, Any],
        input_key: ServiceInputKey,
        ureg: UnitRegistry | None = None,
    ) -> ServiceInputGet:
        data = service["inputs"][input_key]
        port = ServiceInputGet(key_id=input_key, **data)  # validated!
        unit_html: UnitHtmlFormat | None

        if ureg and (unit_html := get_html_formatted_unit(port, ureg)):
            # we know data is ok since it was validated above
            return ServiceInputGet.construct(
                key_id=input_key,
                unit_long=unit_html.long,
                unit_short=unit_html.short,
                **data,
            )
        return port


def _hash_outputs(
    service: dict[str, Any],
    output_key: str,
    *args,  # noqa: ARG001 # pylint: disable=unused-argument
    **kwargs,  # noqa: ARG001 # pylint: disable=unused-argument
):
    return f"{service['key']}/{service['version']}/{output_key}"


class ServiceOutputGetFactory:
    @staticmethod
    @_cachetools_cached(
        cachetools.TTLCache(ttl=_CACHE_TTL, maxsize=_CACHE_MAXSIZE), key=_hash_outputs
    )
    def from_catalog_service_api_model(
        service: dict[str, Any],
        output_key: ServiceOutputKey,
        ureg: UnitRegistry | None = None,
    ) -> ServiceOutputGet:
        data = service["outputs"][output_key]
        # NOTE: prunes invalid field that might have remained in database
        if "defaultValue" in data:
            data.pop("defaultValue")

        # NOTE: this call must be validated if port property type is "ref_contentSchema"
        port = ServiceOutputGet(key_id=output_key, **data)

        unit_html: UnitHtmlFormat | None
        if ureg and (unit_html := get_html_formatted_unit(port, ureg)):
            # we know data is ok since it was validated above
            return ServiceOutputGet.construct(
                key_id=output_key,
                unit_long=unit_html.long,
                unit_short=unit_html.short,
                **data,
            )

        return port
