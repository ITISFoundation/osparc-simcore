""" A collection of free functions to manipulate dicts
"""

from collections.abc import Mapping
from copy import copy, deepcopy
from typing import Any


def remap_keys(data: dict, rename: dict[str, str]) -> dict[str, Any]:
    """A new dict that renames the keys of a dict while keeping the values unchanged

    NOTE: Does not support renaming of nested keys
    """
    return {rename.get(k, k): v for k, v in data.items()}


def get_from_dict(obj: Mapping[str, Any], dotted_key: str, default=None) -> Any:
    keys = dotted_key.split(".")
    value = obj
    for key in keys[:-1]:
        value = value.get(key, {})
    return value.get(keys[-1], default)


def copy_from_dict_ex(data: dict[str, Any], exclude: set[str]) -> dict[str, Any]:
    # NOTE: to be refactored by someone and merged with the next method
    return {k: v for k, v in data.items() if k not in exclude}


def copy_from_dict(
    data: dict[str, Any], *, include: set | dict | None = None, deep: bool = False
):
    #
    # Analogous to advanced includes from pydantic exports
    #   https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude
    #

    if include is None:
        return deepcopy(data) if deep else copy(data)

    if include == ...:
        return deepcopy(data) if deep else copy(data)

    if isinstance(include, set):
        return {key: data[key] for key in include}

    assert isinstance(include, dict)  # nosec

    return {
        key: copy_from_dict(data[key], include=include[key], deep=deep)
        for key in include
    }


def update_dict(obj: dict, **updates):
    for key, update_value in updates.items():
        obj.update(
            {key: update_value(obj[key]) if callable(update_value) else update_value}
        )
    return obj


def assert_equal_ignoring_none(expected: dict, actual: dict):
    for key, exp_value in expected.items():
        if exp_value is None:
            continue
        assert key in actual, f"Missing key {key}"
        act_value = actual[key]
        if isinstance(exp_value, dict) and isinstance(act_value, dict):
            assert_equal_ignoring_none(exp_value, act_value)
        else:
            assert act_value == exp_value, f"Mismatch in {key}: {act_value} != {exp_value}"
