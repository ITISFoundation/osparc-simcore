""" Reusable validators

    Example:

    from pydantic import BaseModel, validator

    class MyModel(BaseModel):
       thumbnail: str | None

       _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
           empty_str_to_none
       )

SEE https://docs.pydantic.dev/usage/validators/#reuse-validators
"""

import enum
from typing import Any


def empty_str_to_none(value: Any):
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def none_to_empty_str(value: Any):
    if value is None:
        return ""
    return value


def create_transform_from_equivalent_enums(enum_cls: type[enum.Enum]):
    def _validator(value: Any):
        if value and not isinstance(value, enum_cls) and isinstance(value, enum.Enum):
            return value.value
        return value

    return _validator
