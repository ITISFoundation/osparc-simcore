from typing import Any, ClassVar, TypeAlias

import orjson
from pydantic import Extra, Field
from pydantic.main import BaseModel

from ..api_schemas_catalog import services
from ..services import ServiceInput, ServiceOutput, ServicePortKey
from ..utils.change_case import snake_to_camel
from ._base import InputSchema, OutputSchema

ServiceInputKey: TypeAlias = ServicePortKey
ServiceOutputKey: TypeAlias = ServicePortKey


def _orjson_dumps(v, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    dump: str = orjson.dumps(v, default=default).decode()
    return dump


class ServiceGet(services.ServiceGet):  # pylint: disable=too-many-ancestors
    class Config(OutputSchema.Config):
        ...


class ServiceUpdate(services.ServiceUpdate):
    class Config(InputSchema.Config):
        ...


class ServiceResourcesGet(services.ServiceResourcesGet):
    class Config(OutputSchema.Config):
        ...


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
        json_dumps = _orjson_dumps
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
