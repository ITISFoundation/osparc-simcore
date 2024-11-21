import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from aiocache import cached  # type: ignore[import-untyped]
from models_library.api_schemas_webserver.catalog import (
    ServiceInputGet,
    ServiceInputKey,
    ServiceOutputGet,
    ServiceOutputKey,
)
from models_library.services import BaseServiceIOModel
from pint import PintError, Quantity, UnitRegistry

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

        q: Quantity = ureg.Quantity(unit_name)
        return UnitHtmlFormat(short=f"{q.units:~H}", long=f"{q.units:H}")
    except (PintError, NotImplementedError):
        return None


#
# Transforms from catalog api models -> webserver api models
#
# Uses aiocache (async) instead of cachetools (sync) in order to handle concurrency better
# SEE https://github.com/ITISFoundation/osparc-simcore/pull/6169
#
_SECOND = 1  # in seconds
_MINUTE = 60 * _SECOND
_CACHE_TTL: Final = 1 * _MINUTE


def _hash_inputs(_f: Callable[..., Any], *_args, **kw):
    assert not _args  # nosec
    service: dict[str, Any] = kw["service"]
    return f"ServiceInputGetFactory_{service['key']}_{service['version']}_{kw['input_key']}"


class ServiceInputGetFactory:
    @staticmethod
    @cached(
        ttl=_CACHE_TTL,
        key_builder=_hash_inputs,
    )
    async def from_catalog_service_api_model(
        *,
        service: dict[str, Any],
        input_key: ServiceInputKey,
        ureg: UnitRegistry | None = None,
    ) -> ServiceInputGet:
        data = service["inputs"][input_key]
        port = ServiceInputGet(key_id=input_key, **data)  # validated!
        unit_html: UnitHtmlFormat | None

        if ureg and (unit_html := get_html_formatted_unit(port, ureg)):
            # we know data is ok since it was validated above
            return ServiceInputGet.model_construct(
                key_id=input_key,
                unit_long=unit_html.long,
                unit_short=unit_html.short,
                **data,
            )
        return port


def _hash_outputs(_f: Callable[..., Any], *_args, **kw):
    assert not _args  # nosec
    service: dict[str, Any] = kw["service"]
    return f"ServiceOutputGetFactory_{service['key']}/{service['version']}/{kw['output_key']}"


class ServiceOutputGetFactory:
    @staticmethod
    @cached(
        ttl=_CACHE_TTL,
        key_builder=_hash_outputs,
    )
    async def from_catalog_service_api_model(
        *,
        service: dict[str, Any],
        output_key: ServiceOutputKey,
        ureg: UnitRegistry | None = None,
    ) -> ServiceOutputGet:
        data = service["outputs"][output_key]
        # NOTE: prunes invalid field that might have remained in database
        data.pop("defaultValue", None)

        # NOTE: this call must be validated if port property type is "ref_contentSchema"
        port = ServiceOutputGet(key_id=output_key, **data)

        unit_html: UnitHtmlFormat | None
        if ureg and (unit_html := get_html_formatted_unit(port, ureg)):
            # we know data is ok since it was validated above
            return ServiceOutputGet.model_construct(
                key_id=output_key,
                unit_long=unit_html.long,
                unit_short=unit_html.short,
                **data,
            )

        return port
