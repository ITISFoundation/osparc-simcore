from typing import Any, TypeAlias

import orjson
from models_library.services import (
    ServiceInput,
    ServiceKey,
    ServiceOutput,
    ServicePortKey,
    ServiceVersion,
)
from models_library.utils.change_case import snake_to_camel
from pint import UnitRegistry
from pydantic import Extra, Field
from pydantic.main import BaseModel

from ._units import UnitHtmlFormat, get_html_formatted_unit

ServiceInputKey: TypeAlias = ServicePortKey
ServiceOutputKey: TypeAlias = ServicePortKey


def json_dumps(v, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    dump: str = orjson.dumps(v, default=default).decode()
    return dump


#####
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
        schema_extra = {
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
        schema_extra = {
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


#######################
# Helper functions
#


def replace_service_input_outputs(
    service: dict[str, Any],
    *,
    unit_registry: UnitRegistry | None = None,
    **export_options,
):
    """Thin wrapper to replace i/o ports in returned service model"""
    # This is a fast solution until proper models are available for the web API

    for input_key in service["inputs"]:
        new_input = ServiceInputGet.from_catalog_service_api_model(
            service, input_key, unit_registry
        )
        service["inputs"][input_key] = new_input.dict(**export_options)

    for output_key in service["outputs"]:
        new_output = ServiceOutputGet.from_catalog_service_api_model(
            service, output_key, unit_registry
        )
        service["outputs"][output_key] = new_output.dict(**export_options)


assert ServiceKey  # nosec
assert ServiceVersion  # nosec

__all__: tuple[str, ...] = ("ServiceKey", "ServiceVersion")
