from typing import Optional

from models_library.services import (
    KEY_RE,
    VERSION_RE,
    PropertyName,
    ServiceInput,
    ServiceOutput,
)
from pydantic import Extra, Field, constr

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
# TODO: uuid instead of key+version?

INPUT_SAMPLE = {
    "displayOrder": 2,
    "label": "Sleep Time",
    "description": "Time to wait before completion",
    "type": "number",
    "fileToKeyMap": {},
    "defaultValue": 0,
    "unit": "second",
    "widget": {"type": "TextArea", "details": {"minHeight": 0}},
    "keyId": "input_2",
    "unitLong": "seconds",
    "unitShort": "sec",
}

OUTPUT_SAMPLE = {
    "displayOrder": 2,
    "label": "Time Slept",
    "description": "Time the service waited before completion",
    "type": "number",
    "fileToKeyMap": {},
    "defaultValue": 0,
    "unit": "second",
    "keyId": "output_2",
}


class ServiceInputApiOut(ServiceInput):
    key_id: ServiceInputKey = Field(
        ..., description="Unique name identifier for this input"
    )
    unit_long: Optional[str] = Field(
        None, description="Long name of the unit, if available"
    )
    unit_short: Optional[str] = Field(
        None, description="Short name for the unit, if available"
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        schema_extra = {"example": INPUT_SAMPLE}


class ServiceOutputApiOut(ServiceOutput):
    key_id: ServiceInputKey = Field(
        ..., description="Unique name identifier for this input"
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        schema_extra = {"example": INPUT_SAMPLE}
