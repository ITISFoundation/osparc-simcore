from typing import Any, Dict, Optional

import orjson
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


# TODO: will be replaced by pynt functionality
FAKE_UNIT_TO_FORMATS = {"SECOND": ("s", "seconds"), "METER": ("m", "meters")}


def get_formatted_unit(data: dict):
    unit = data.get("unit")
    if unit:
        return FAKE_UNIT_TO_FORMATS.get(unit.upper(), [None, None])
    return [None, None]


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
        None, description="Long name of the unit, if available"
    )
    unit_short: Optional[str] = Field(
        None, description="Short name for the unit, if available"
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        json_loads = orjson.loads
        json_dumps = json_dumps


class ServiceInputApiOut(ServiceInput, _BaseCommonApiExtension):
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
            }
        }

    @classmethod
    def from_catalog_service(cls, service: Dict[str, Any], input_key: ServiceInputKey):
        data = service["inputs"][input_key]
        ushort, ulong = get_formatted_unit(data)

        return cls(keyId=input_key, unitLong=ulong, unitShort=ushort, **data)


class ServiceOutputApiOut(ServiceOutput, _BaseCommonApiExtension):
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
    def from_catalog_service(
        cls, service: Dict[str, Any], output_key: ServiceOutputKey
    ):
        data = service["outputs"][output_key]
        ushort, ulong = get_formatted_unit(data)

        return cls(keyId=output_key, unitLong=ulong, unitShort=ushort, **data)


#######################
# Helper functions
#


def replace_service_input_outputs(service: Dict[str, Any], **export_options):
    """ Thin wrapper to replace i/o ports in returned service model """
    # This is a fast solution until proper models are available for the web API
    # TODO: from models_library.api_schemas_catalog

    for input_key in service["inputs"]:
        new_input = ServiceInputApiOut.from_catalog_service(service, input_key)
        service["inputs"][input_key] = new_input.dict(**export_options)

    for output_key in service["outputs"]:
        new_output = ServiceOutputApiOut.from_catalog_service(service, output_key)
        service["outputs"][output_key] = new_output.dict(**export_options)
