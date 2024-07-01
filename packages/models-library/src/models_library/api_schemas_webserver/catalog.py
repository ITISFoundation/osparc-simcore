from typing import Any, ClassVar, TypeAlias

from pydantic import Extra, Field
from pydantic.main import BaseModel

from ..api_schemas_catalog import services as api_schemas_catalog_services
from ..services_history import ServiceRelease
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
    **api_schemas_catalog_services.ServiceGet.Config.schema_extra["example"],
    **{
        "inputs": {
            f"input{i}": example
            for i, example in enumerate(ServiceInputGet.Config.schema_extra["examples"])
        },
        "outputs": {"outFile": ServiceOutputGet.Config.schema_extra["example"]},
    },
}


_EXAMPLE_SLEEPER: dict[str, Any] = {
    "name": "sleeper",
    "thumbnail": None,
    "description": "A service which awaits for time to pass, two times.",
    "classifiers": [],
    "quality": {},
    "accessRights": {"1": {"execute_access": True, "write_access": False}},
    "key": "simcore/services/comp/itis/sleeper",
    "version": "2.2.1",
    "version_display": "2 Xtreme",
    "integration-version": "1.0.0",
    "type": "computational",
    "authors": [
        {
            "name": "Author Bar",
            "email": "author@acme.com",
            "affiliation": "ACME",
        },
    ],
    "contact": "contact@acme.com",
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
    "owner": "owner@acme.com",
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
        schema_extra: ClassVar[dict[str, Any]] = {"example": _EXAMPLE_FILEPICKER}


class ServiceUpdate(api_schemas_catalog_services.ServiceUpdate):
    class Config(InputSchema.Config):
        ...


class ServiceResourcesGet(api_schemas_catalog_services.ServiceResourcesGet):
    class Config(OutputSchema.Config):
        ...


class DEVServiceGet(ServiceGet):
    # pylint: disable=too-many-ancestors

    history: list[ServiceRelease] = Field(
        default=[],
        description="history of releases for this service at this point in time, starting from the newest to the oldest."
        " It includes current release.",
    )

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    **_EXAMPLE_SLEEPER,  # v2.2.1  (latest)
                    "history": [
                        {
                            "version": _EXAMPLE_SLEEPER["version"],
                            "version_display": "Summer Release",
                            "release_date": "2024-07-20T15:00:00",
                        },
                        {
                            "version": "2.0.0",
                            "compatibility": {
                                "can_update_to": _EXAMPLE_SLEEPER["version"],
                            },
                        },
                        {"version": "0.9.11"},
                        {"version": "0.9.10"},
                        {
                            "version": "0.9.8",
                            "compatibility": {
                                "can_update_to": "0.9.11",
                            },
                        },
                        {
                            "version": "0.9.1",
                            "version_display": "Matterhorn",
                            "release_date": "2024-01-20T18:49:17",
                            "compatibility": {
                                "can_update_to": "0.9.11",
                            },
                        },
                        {"version": "0.9.0"},
                        {"version": "0.8.0"},
                        {"version": "0.1.0"},
                    ],
                },
                {
                    **_EXAMPLE_FILEPICKER,
                    "history": [
                        {
                            "version": _EXAMPLE_FILEPICKER["version"],
                            "version_display": "Odei Release",
                            "release_date": "2025-03-25T00:00:00",
                        }
                    ],
                },
            ]
        }
