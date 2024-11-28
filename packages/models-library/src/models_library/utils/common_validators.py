""" Reusable validators

    Example:

    from pydantic import BaseModel, validator
    from models_library.utils.common_validators import empty_str_to_none_pre_validator

    class MyModel(BaseModel):
       thumbnail: str | None

       _empty_is_none = validator("thumbnail", mode="before")(
           empty_str_to_none_pre_validator
       )

SEE https://docs.pydantic.dev/usage/validators/#reuse-validators
"""

import enum
import functools
import operator
from typing import Any

from common_library.json_serialization import json_loads
from orjson import JSONDecodeError
from pydantic import BaseModel


def empty_str_to_none_pre_validator(value: Any):
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def none_to_empty_str_pre_validator(value: Any):
    if value is None:
        return ""
    return value


def none_to_empty_list_pre_validator(value: Any):
    if value is None:
        return []
    return value


def parse_json_pre_validator(value: Any):
    if isinstance(value, str):
        try:
            return json_loads(value)
        except JSONDecodeError as err:
            msg = f"Invalid JSON {value=}: {err}"
            raise ValueError(msg) from err
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


def null_or_none_str_to_none_validator(value: Any):
    if isinstance(value, str) and value.lower() in ("null", "none"):
        return None
    return value


def create__check_only_one_is_set__root_validator(alternative_field_names: list[str]):
    """Ensure exactly one and only one of the alternatives is set

    NOTE: a field is considered here `unset` when it is `not None`. When None
    is used to indicate something else, please do not use this validator.

    This is useful when you want to give the client alternative
    ways to set the same thing e.g. set the user by email or id or username
    and each of those has a different field

    NOTE: Alternatevely, the previous example can also be solved using a
    single field as `user: Email | UserID | UserName`

    SEE test_uid_or_email_are_set.py for more details
    """

    def _validator(cls: type[BaseModel], values):
        assert set(alternative_field_names).issubset(cls.model_fields)  # nosec

        got = {
            field_name: getattr(values, field_name)
            for field_name in alternative_field_names
        }

        if not functools.reduce(operator.xor, (v is not None for v in got.values())):
            msg = (
                f"Either { 'or'.join(got.keys()) } must be set, but not both. Got {got}"
            )
            raise ValueError(msg)
        return values

    return _validator
