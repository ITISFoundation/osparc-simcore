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


def empty_str_to_none_pre_validator(value: Any):
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def none_to_empty_str_pre_validator(value: Any):
    if value is None:
        return ""
    return value


def create_enums_pre_validator(enum_cls: type[enum.Enum]):
    """Enables parsing enums from equivalent enums

    SEE test__pydantic_models_and_enumps.py for more details
    """

    def _validator(value: Any):
        if value and not isinstance(value, enum_cls) and isinstance(value, enum.Enum):
            return value.value
        return value

    return _validator
