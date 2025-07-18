import logging
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Final

from aiocache import cached  # type: ignore[import-untyped]
from aiohttp import web
from aiohttp.web import Request
from models_library.api_schemas_webserver.catalog import (
    ServiceInputGet,
    ServiceInputKey,
    ServiceOutputGet,
    ServiceOutputKey,
)
from models_library.basic_types import IdInt
from models_library.rest_pagination import PageQueryParameters
from models_library.services import BaseServiceIOModel, ServiceKey, ServiceVersion
from models_library.users import UserID
from pint import PintError, Quantity, UnitRegistry
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from servicelib.aiohttp.requests_validation import handle_validation_as_http_error

from ..constants import RQ_PRODUCT_KEY, RQT_USERID_KEY

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


class CatalogRequestContext(BaseModel):
    app: web.Application
    user_id: UserID
    product_name: str
    unit_registry: UnitRegistry
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(cls, request: Request) -> "CatalogRequestContext":
        with handle_validation_as_http_error(
            error_msg_template="Invalid request",
            resource_name=request.rel_url.path,
        ):
            assert request.app  # nosec
            return cls(
                app=request.app,
                user_id=request[RQT_USERID_KEY],
                product_name=request[RQ_PRODUCT_KEY],
                unit_registry=request.app[UnitRegistry.__name__],
            )


class ServicePathParams(BaseModel):
    service_key: ServiceKey
    service_version: ServiceVersion
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )

    @field_validator("service_key", mode="before")
    @classmethod
    def _ensure_unquoted(cls, v):
        # NOTE: this is needed as in pytest mode, the aiohttp server does not seem to unquote automatically
        if v is not None:
            return urllib.parse.unquote(v)
        return v


class ListServiceParams(PageQueryParameters): ...


class ServiceTagPathParams(ServicePathParams):
    tag_id: IdInt


class ServiceInputsPathParams(ServicePathParams):
    input_key: ServiceInputKey


class FromServiceOutputQueryParams(BaseModel):
    from_service_key: Annotated[ServiceKey, Field(alias="fromService")]
    from_service_version: Annotated[ServiceVersion, Field(alias="fromVersion")]
    from_output_key: Annotated[ServiceOutputKey, Field(alias="fromOutput")]


class ServiceOutputsPathParams(ServicePathParams):
    output_key: ServiceOutputKey


class ToServiceInputsQueryParams(BaseModel):
    to_service_key: Annotated[ServiceKey, Field(alias="toService")]
    to_service_version: Annotated[ServiceVersion, Field(alias="toVersion")]
    to_input_key: Annotated[ServiceInputKey, Field(alias="toInput")]
