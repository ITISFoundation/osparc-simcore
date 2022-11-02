from typing import Any, Optional

import orjson
from models_library.services import (
    KEY_RE,
    VERSION_RE,
    ServiceInput,
    ServiceOutput,
    ServicePortKey,
)
from models_library.utils.change_case import snake_to_camel
from pint import UnitRegistry
from pydantic import Extra, Field, constr
from pydantic.main import BaseModel

from .catalog_units import UnitHtmlFormat, get_html_formatted_unit

ServiceKey = constr(regex=KEY_RE)
ServiceVersion = constr(regex=VERSION_RE)
ServiceInputKey = ServicePortKey
ServiceOutputKey = ServicePortKey


def json_dumps(v, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default).decode()


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
#
# TODO: reduce to a minimum returned input/output models (ask OM)
class _BaseCommonApiExtension(BaseModel):
    unit_long: Optional[str] = Field(
        None,
        description="Long name of the unit for display (html-compatible), if available",
    )
    unit_short: Optional[str] = Field(
        None,
        description="Short name for the unit for display (html-compatible), if available",
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        json_loads = orjson.loads
        json_dumps = json_dumps


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
        ureg: Optional[UnitRegistry] = None,
    ):
        data = service["inputs"][input_key]
        port = cls(keyId=input_key, **data)  # validated!
        unit_html: UnitHtmlFormat

        if ureg and (unit_html := get_html_formatted_unit(port, ureg)):
            # we know data is ok since it was validated above
            return cls.construct(
                keyId=input_key,
                unitLong=unit_html.long,
                unitShort=unit_html.short,
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
        ureg: Optional[UnitRegistry] = None,
    ):
        data = service["outputs"][output_key]
        # NOTE: prunes invalid field that might have remained in database
        # TODO: remove from root and remove this cleanup operation
        if "defaultValue" in data:
            data.pop("defaultValue")

        port = cls(keyId=output_key, **data)  # validated

        unit_html: UnitHtmlFormat
        if ureg and (unit_html := get_html_formatted_unit(port, ureg)):
            # we know data is ok since it was validated above
            return cls.construct(
                keyId=output_key,
                unitLong=unit_html.long,
                unitShort=unit_html.short,
                **data,
            )
        return port


#######################
# Helper functions
#


def replace_service_input_outputs(
    service: dict[str, Any],
    *,
    unit_registry: Optional[UnitRegistry] = None,
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
