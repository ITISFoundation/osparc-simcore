from copy import deepcopy
from typing import Any

from toolz.dicttoolz import get_in, update_in


def merge_extend(
    a: dict[str, Any],
    b: dict[str, Any],
    *,
    extendable_array_keys: tuple[list[str], ...],
    extendable_dict_keys: tuple[list[str], ...],
) -> dict[str, Any]:
    """returns dict which results of merging a with b by extending
    the fields defined in extendable_array_keys and extendable_dict_keys

    example:
    a={"labels"{"subentry":[1,2]}}
    b={"labels":{"subentry":[3,6]}}
    extendable_array_keys=(["labels", "subentry"])
    --> result={"labels"{"subentry":[1,2,3,6]}}

    """
    merged_dict = deepcopy(a)
    for keys_path in extendable_array_keys:
        merged_dict = update_in(
            merged_dict,
            keys_path,
            lambda value, keys_path=keys_path, b=b: (value or [])
            + get_in(keys_path, b, []),
        )
    for keys_path in extendable_dict_keys:
        merged_dict = update_in(
            merged_dict,
            keys_path,
            lambda value, keys_path=keys_path, b=b: (value or {})
            | get_in(keys_path, b, {}),
        )
    return merged_dict
