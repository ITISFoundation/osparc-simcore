from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from .basic_types import EnvVarKey


class BootChoice(TypedDict):
    label: str
    description: str


class BootOption(BaseModel):
    label: str
    description: str
    default: str
    items: dict[str, BootChoice]

    @field_validator("items")
    @classmethod
    def ensure_default_included(cls, v, info: ValidationInfo):
        default = info.data["default"]
        if default not in v:
            msg = f"Expected default={default} to be present a key of items={v}"
            raise ValueError(msg)
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "label": "Boot mode",
                    "description": "Start it in web page mode",
                    "default": "0",
                    "items": {
                        "0": {
                            "label": "Non Voila",
                            "description": "Tooltip for non Voila boot mode",
                        },
                        "1": {
                            "label": "Voila",
                            "description": "Tooltip for Voila boot mode",
                        },
                    },
                },
                {
                    "label": "Application theme",
                    "description": "Select a theme for the application",
                    "default": "b",
                    "items": {
                        "a": {
                            "label": "Clear",
                            "description": "Using white background",
                        },
                        "b": {
                            "label": "Dark",
                            "description": "Using black and gray tones",
                        },
                    },
                },
            ]
        }
    )


BootOptions = dict[EnvVarKey, BootOption]
