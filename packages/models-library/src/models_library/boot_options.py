from typing import Dict, Optional

from pydantic import BaseModel, constr, root_validator
from typing_extensions import TypedDict

ENV_VAR_KEY_RE = r"[a-zA-Z][a-azA-Z0-9_]*"
EnvVarKey = constr(regex=ENV_VAR_KEY_RE)


class BootOptionItem(TypedDict):
    label: str
    description: str


class BootOptionMode(BaseModel):
    label: str
    description: str
    default: str
    items: Dict[str, BootOptionItem]

    @root_validator
    @classmethod
    def ensure_default_is_present(cls, values: Dict) -> Dict:
        default = values["default"]
        items = values["items"]
        if default not in items:
            raise ValueError(
                f"Expected default={default} to be present a key of items={items}"
            )
        return values

    class Config:
        schema_extra = {
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


BootOptions = Optional[Dict[EnvVarKey, BootOptionMode]]
