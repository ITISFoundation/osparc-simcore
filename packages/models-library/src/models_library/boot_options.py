from pydantic import BaseModel, ConfigDict, validator
from typing_extensions import TypedDict

from .basic_types import EnvVarKey


class BootChoice(TypedDict):
    label: str
    description: str


class BootOption(BaseModel):
    label: str
    description: str
    default: str
    items: dict[str, BootChoice]

    # TODO[pydantic]: We couldn't refactor the `validator`, please replace it by `field_validator` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-validators for more information.
    @validator("items")
    @classmethod
    def ensure_default_included(cls, v, values):
        default = values["default"]
        if default not in v:
            msg = f"Expected default={default} to be present a key of items={v}"
            raise ValueError(msg)
        return v

    model_config = ConfigDict()


BootOptions = dict[EnvVarKey, BootOption]
