from copy import deepcopy
from typing import Any, ClassVar, TypeAlias

from pydantic import Extra, Field
from pydantic.main import BaseModel

from ..api_schemas_catalog import services as api_schemas_catalog_services
from ..services import ServiceInput, ServiceOutput, ServicePortKey
from ..utils.change_case import snake_to_camel
from ..utils.json_serialization import json_dumps, json_loads
from ._base import InputSchema, OutputSchema

ServiceInputKey: TypeAlias = ServicePortKey
ServiceOutputKey: TypeAlias = ServicePortKey


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
        json_loads = json_loads


class ServiceInputGet(ServiceInput, _BaseCommonApiExtension):
    """Extends fields of api_schemas_catalog.services.ServiceGet.outputs[*]"""

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
    """Extends fields of api_schemas_catalog.services.ServiceGet.outputs[*]"""

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


ServiceInputsGetDict: TypeAlias = dict[ServicePortKey, ServiceInputGet]
ServiceOutputsGetDict: TypeAlias = dict[ServicePortKey, ServiceOutputGet]


_EXAMPLE: dict[str, Any] = deepcopy(
    api_schemas_catalog_services.ServiceGet.Config.schema_extra["example"]
)
_EXAMPLE.update(
    {
        "inputs": {
            f"input{i}": example
            for i, example in enumerate(ServiceInputGet.Config.schema_extra["examples"])
        },
        "outputs": {"outFile": ServiceOutputGet.Config.schema_extra["example"]},
    }
)


class ServiceGet(api_schemas_catalog_services.ServiceGet):
    # pylint: disable=too-many-ancestors
    inputs: ServiceInputsGetDict = Field(  # type: ignore[assignment]
        ..., description="inputs with extended information"
    )
    outputs: ServiceOutputsGetDict = Field(  # type: ignore[assignment]
        ..., description="outputs with extended information"
    )

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {"example": _EXAMPLE}


class ServiceUpdate(api_schemas_catalog_services.ServiceUpdate):
    class Config(InputSchema.Config):
        ...


class ServiceResourcesGet(api_schemas_catalog_services.ServiceResourcesGet):
    class Config(OutputSchema.Config):
        ...
