""" Reusable validators

    Example:

    from pydantic import BaseModel, validator
    from models_library.utils.common_validators import empty_str_to_none_pre_validator

    class MyModel(BaseModel):
       thumbnail: str | None

       _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
           empty_str_to_none_pre_validator
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


def ensure_unique_list_values_validator(list_data: list) -> list:
    if len(list_data) != len(set(list_data)):
        msg = f"List values must be unique, provided: {list_data}"
        raise ValueError(msg)
    return list_data


def ensure_unique_dict_values_validator(dict_data: dict) -> dict:
    if len(dict_data) != len(set(dict_data.values())):
        msg = f"Dictionary values must be unique, provided: {dict_data}"
        raise ValueError(msg)
    return dict_data
