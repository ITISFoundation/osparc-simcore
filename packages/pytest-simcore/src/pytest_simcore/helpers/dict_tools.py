""" Utils to operate with dicts """

from copy import deepcopy
from typing import Any, Mapping

ConfigDict = dict[str, Any]


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
        return deepcopy(data) if deep else data.copy()

    if include == ...:
        return deepcopy(data) if deep else data.copy()

    if isinstance(include, set):
        return {key: data[key] for key in include}

    assert isinstance(include, dict)  # nosec

    return {
        key: copy_from_dict(data[key], include=include[key], deep=deep)
        for key in include
    }


def update_dict(obj: dict, **updates):
    for key, update_value in updates.items():
        if callable(update_value):
            update_value = update_value(obj[key])
        obj.update({key: update_value})
    return obj
