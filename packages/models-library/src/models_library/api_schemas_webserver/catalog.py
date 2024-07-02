from typing import Any, ClassVar, TypeAlias

from pydantic import Extra, Field
from pydantic.main import BaseModel

from ..api_schemas_catalog import services as api_schemas_catalog_services
from ..services_io import ServiceInput, ServiceOutput
from ..services_types import ServicePortKey
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


_EXAMPLE_FILEPICKER: dict[str, Any] = {
    **api_schemas_catalog_services.ServiceGet.Config.schema_extra["examples"][1],
    "inputs": {},
    "outputs": {
        "outFile": {
            "displayOrder": 0,
            "label": "File",
            "description": "Chosen File",
            "type": "data:*/*",
            "fileToKeyMap": None,
            "keyId": "outFile",
        }
    },
}

_EXAMPLE_SLEEPER: dict[str, Any] = {
    **api_schemas_catalog_services.ServiceGet.Config.schema_extra["examples"][0],
    "inputs": {
        "input_1": {
            "displayOrder": 1,
            "label": "File with int number",
            "description": "Pick a file containing only one integer",
            "type": "data:text/plain",
            "fileToKeyMap": {"single_number.txt": "input_1"},
            "keyId": "input_1",
        },
        "input_2": {
            "unitLong": "second",
            "unitShort": "s",
            "label": "Sleep interval",
            "description": "Choose an amount of time to sleep in range [0:]",
            "keyId": "input_2",
            "displayOrder": 2,
            "type": "ref_contentSchema",
            "contentSchema": {
                "title": "Sleep interval",
                "type": "integer",
                "x_unit": "second",
                "minimum": 0,
            },
            "defaultValue": 2,
        },
        "input_3": {
            "displayOrder": 3,
            "label": "Fail after sleep",
            "description": "If set to true will cause service to fail after it sleeps",
            "type": "boolean",
            "defaultValue": False,
            "keyId": "input_3",
        },
        "input_4": {
            "unitLong": "meter",
            "unitShort": "m",
            "label": "Distance to bed",
            "description": "It will first walk the distance to bed",
            "keyId": "input_4",
            "displayOrder": 4,
            "type": "ref_contentSchema",
            "contentSchema": {
                "title": "Distance to bed",
                "type": "integer",
                "x_unit": "meter",
            },
            "defaultValue": 0,
        },
        "input_5": {
            "unitLong": "byte",
            "unitShort": "B",
            "label": "Dream (or nightmare) of the night",
            "description": "Defines the size of the dream that will be generated [0:]",
            "keyId": "input_5",
            "displayOrder": 5,
            "type": "ref_contentSchema",
            "contentSchema": {
                "title": "Dream of the night",
                "type": "integer",
                "x_unit": "byte",
                "minimum": 0,
            },
            "defaultValue": 0,
        },
    },
    "outputs": {
        "output_1": {
            "displayOrder": 1,
            "label": "File containing one random integer",
            "description": "Integer is generated in range [1-9]",
            "type": "data:text/plain",
            "fileToKeyMap": {"single_number.txt": "output_1"},
            "keyId": "output_1",
        },
        "output_2": {
            "unitLong": "second",
            "unitShort": "s",
            "label": "Random sleep interval",
            "description": "Interval is generated in range [1-9]",
            "keyId": "output_2",
            "displayOrder": 2,
            "type": "ref_contentSchema",
            "contentSchema": {
                "title": "Random sleep interval",
                "type": "integer",
                "x_unit": "second",
            },
        },
        "output_3": {
            "displayOrder": 3,
            "label": "Dream output",
            "description": "Contains some random data representing a dream",
            "type": "data:text/plain",
            "fileToKeyMap": {"dream.txt": "output_3"},
            "keyId": "output_3",
        },
    },
}


class ServiceGet(api_schemas_catalog_services.ServiceGet):
    # pylint: disable=too-many-ancestors
    inputs: ServiceInputsGetDict = Field(  # type: ignore[assignment]
        ..., description="inputs with extended information"
    )
    outputs: ServiceOutputsGetDict = Field(  # type: ignore[assignment]
        ..., description="outputs with extended information"
    )

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [_EXAMPLE_FILEPICKER, _EXAMPLE_SLEEPER]
        }


class ServiceUpdate(api_schemas_catalog_services.ServiceUpdate):
    class Config(InputSchema.Config):
        ...


class ServiceResourcesGet(api_schemas_catalog_services.ServiceResourcesGet):
    class Config(OutputSchema.Config):
        ...


# TODO: reduces


class CatalogServiceGet(api_schemas_catalog_services.ServiceGetV2):
    # NOTE: will replace ServiceGet!

    # pylint: disable=too-many-ancestors
    inputs: ServiceInputsGetDict = Field(  # type: ignore[assignment]
        ..., description="inputs with extended information"
    )
    outputs: ServiceOutputsGetDict = Field(  # type: ignore[assignment]
        ..., description="outputs with extended information"
    )

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                **api_schemas_catalog_services.ServiceGetV2.Config.schema_extra[
                    "examples"
                ][0],
                "inputs": {
                    f"input{i}": example
                    for i, example in enumerate(
                        ServiceInputGet.Config.schema_extra["examples"]
                    )
                },
                "outputs": {"outFile": ServiceOutputGet.Config.schema_extra["example"]},
            }
        }
