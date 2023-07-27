from dataclasses import dataclass
from typing import Any, ClassVar, TypeAlias

import orjson
from models_library.services import (
    BaseServiceIOModel,
    ServiceInput,
    ServiceOutput,
    ServicePortKey,
)
from models_library.utils.change_case import snake_to_camel
from pint import PintError, UnitRegistry
from pydantic import Extra, Field
from pydantic.main import BaseModel

from ..api_schemas_catalog import services
from ._base import InputSchema, OutputSchema

ServiceInputKey: TypeAlias = ServicePortKey
ServiceOutputKey: TypeAlias = ServicePortKey


def json_dumps(v, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    dump: str = orjson.dumps(v, default=default).decode()
    return dump


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


class ServiceGet(services.ServiceGet):
    class Config(OutputSchema.Config):
        ...


class ServiceUpdate(services.ServiceUpdate):
    class Config(InputSchema.Config):
        ...


class ServiceResourcesGet(services.ServiceResourcesGet):
    class Config(OutputSchema.Config):
        ...


#
#  API models specifics to front-end needs
#
# Using WebApi prefix and In/Out suffix to distinguish web API models
#  - internal domain models should be consise, non-verbose, minimal, correct
#  - API models should be adapted to API user needs
#  - warning with couplings! Add example to ensure that API model maintain
#    backwards compatibility
#   - schema samples could have multiple schemas to tests backwards compatibility


class _BaseCommonApiExtension(BaseModel):
    unit_long: str | None = Field(
        None,
        description="Long name of the unit for display (html-compatible), if available",
    )
    unit_short: str | None = Field(
        None,
        description="Short name for the unit for display (html-compatible), if available",
    )

    class Config:
        alias_generator = snake_to_camel
        allow_population_by_field_name = True
        extra = Extra.forbid
        json_dumps = json_dumps
        json_loads = orjson.loads


class ServiceInputGet(ServiceInput, _BaseCommonApiExtension):
    key_id: ServiceInputKey = Field(
        ..., description="Unique name identifier for this input"
    )

    class Config(_BaseCommonApiExtension.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "displayOrder": 2,
                "label": "Sleep Time",
                "description": "Time to wait before completion",
                "type": "number",
                "defaultValue": 0,
                "unit": "second",
                "widget": {"type": "TextArea", "details": {"minHeight": 1}},
                "keyId": "input_2",
                "unitLong": "seconds",
                "unitShort": "sec",
            },
            "examples": [
                # uses content-schema
                {
                    "label": "Acceleration",
                    "description": "acceleration with units",
                    "type": "ref_contentSchema",
                    "contentSchema": {
                        "title": "Acceleration",
                        "type": "number",
                        "x_unit": "m/s**2",
                    },
                    "keyId": "input_1",
                    "unitLong": "meter/second<sup>3</sup>",
                    "unitShort": "m/s<sup>3</sup>",
                }
            ],
        }

    @classmethod
    def from_catalog_service_api_model(
        cls,
        service: dict[str, Any],
        input_key: ServiceInputKey,
        ureg: UnitRegistry | None = None,
    ):
        data = service["inputs"][input_key]
        port = cls(key_id=input_key, **data)  # validated!
        unit_html: UnitHtmlFormat | None

        if ureg and (unit_html := get_html_formatted_unit(port, ureg)):
            # we know data is ok since it was validated above
            return cls.construct(
                key_id=input_key,
                unit_long=unit_html.long,
                unit_short=unit_html.short,
                **data,
            )
        return port


class ServiceOutputGet(ServiceOutput, _BaseCommonApiExtension):
    key_id: ServiceOutputKey = Field(
        ..., description="Unique name identifier for this input"
    )

    class Config(_BaseCommonApiExtension.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "displayOrder": 2,
                "label": "Time Slept",
                "description": "Time the service waited before completion",
                "type": "number",
                "unit": "second",
                "unitLong": "seconds",
                "unitShort": "sec",
                "keyId": "output_2",
            }
        }

    @classmethod
    def from_catalog_service_api_model(
        cls,
        service: dict[str, Any],
        output_key: ServiceOutputKey,
        ureg: UnitRegistry | None = None,
    ) -> "ServiceOutputGet":
        data = service["outputs"][output_key]
        # NOTE: prunes invalid field that might have remained in database
        if "defaultValue" in data:
            data.pop("defaultValue")

        port = cls(key_id=output_key, **data)  # validated

        unit_html: UnitHtmlFormat | None
        if ureg and (unit_html := get_html_formatted_unit(port, ureg)):
            # we know data is ok since it was validated above
            return cls.construct(
                key_id=output_key,
                unit_long=unit_html.long,
                unit_short=unit_html.short,
                **data,
            )

        return port
