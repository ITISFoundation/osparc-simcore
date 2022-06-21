""" Utils to operate with dicts """

from typing import Any, Mapping, Optional, Union

ConfigDict = dict[str, Any]


def get_from_dict(obj: Mapping[str, Any], dotted_key: str, default=None) -> Any:
    keys = dotted_key.split(".")
    value = obj
    for key in keys[:-1]:
        value = value.get(key, {})
    return value.get(keys[-1], default)


def copy_from_dict(data: dict[str, Any], *, include: Optional[Union[set, dict]] = None):
    #
    # Analogous to advanced includes from pydantic exports
    #   https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude
    #

    if include is None:
        return data.copy()

    if include == ...:
        return data

    if isinstance(include, set):
        return {key: data[key] for key in include}

    assert isinstance(include, dict)  # nosec

    return {key: copy_from_dict(data[key], include=include[key]) for key in include}


def update_dict(obj: dict, **updates):
    for key, update_value in updates.items():
        if callable(update_value):
            update_value = update_value(obj[key])
        obj.update({key: update_value})
    return obj
