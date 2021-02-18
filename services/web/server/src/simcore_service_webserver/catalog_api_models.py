from typing import Any, Dict, Optional

from models_library.services import (
    KEY_RE,
    VERSION_RE,
    PropertyName,
    ServiceInput,
    ServiceOutput,
)
from pydantic import Extra, Field, constr
from pydantic.main import BaseModel

from .utils import snake_to_camel

ServiceKey = constr(regex=KEY_RE)
ServiceVersion = constr(regex=VERSION_RE)


ServiceInputKey = PropertyName
ServiceOutputKey = PropertyName


# Using ApiOut/ApiIn suffix to distinguish API models vs internal domain model
#  - internal domain models should be consise, non-verbose, minimal, correct
#  - API models should be adapted to API user needs
#  - warning with couplings! Add example to ensure that API model maintain
#    backwards compatibility
#   - schema samples could have multiple schemas to tests backwards compatibility
#
# TODO: reduce to a minimum returned input/output models (ask OM)
#
INPUT_SAMPLE = {
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
}

OUTPUT_SAMPLE = {
    "displayOrder": 2,
    "label": "Time Slept",
    "description": "Time the service waited before completion",
    "type": "number",
    "unit": "second",
    "unitLong": "seconds",
    "unitShort": "sec",
    "keyId": "output_2",
}


# TODO: will be replaced by pynt functionality
FAKE_UNIT_TO_FORMATS = {"SECOND": ("s", "seconds"), "METER": ("m", "meters")}


def get_formatted_unit(data: dict):
    unit = data.get("unit")
    if unit:
        return FAKE_UNIT_TO_FORMATS.get(unit.upper(), [None, None])
    return [None, None]


class _CommonApiExtension(BaseModel):
    unit_long: Optional[str] = Field(
        None, description="Long name of the unit, if available"
    )
    unit_short: Optional[str] = Field(
        None, description="Short name for the unit, if available"
    )


class ServiceInputApiOut(ServiceInput, _CommonApiExtension):
    key_id: ServiceInputKey = Field(
        ..., description="Unique name identifier for this input"
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        schema_extra = {"example": INPUT_SAMPLE}

    @classmethod
    def from_service(cls, service: Dict[str, Any], input_key: ServiceInputKey):
        data = service["inputs"][input_key]
        ushort, ulong = get_formatted_unit(data)

        return cls(keyId=input_key, unitLong=ulong, unitShort=ushort, **data)


class ServiceOutputApiOut(ServiceOutput, _CommonApiExtension):
    key_id: ServiceOutputKey = Field(
        ..., description="Unique name identifier for this input"
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        schema_extra = {"example": OUTPUT_SAMPLE}

    @classmethod
    def from_service(cls, service: Dict[str, Any], output_key: ServiceOutputKey):
        data = service["outputs"][output_key]
        ushort, ulong = get_formatted_unit(data)

        return cls(keyId=output_key, unitLong=ulong, unitShort=ushort, **data)


# TODO: from models_library.api_schemas_catalog
