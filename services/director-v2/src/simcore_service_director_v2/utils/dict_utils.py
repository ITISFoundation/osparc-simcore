from copy import deepcopy
from typing import Any, Optional

from toolz.dicttoolz import get_in, update_in


def nested_update(
    a: dict[str, Any], b: dict[str, Any], *, include: tuple[list[str], ...]
) -> dict[str, Any]:
    """returns dict which results of updating a with b on selected key paths
    by merging dictionaries and extending arrays with what is found in b
    Only the fields defined in

    example:
    a={"labels"{"subentry":[1,2]}}
    b={"labels":{"subentry":[3,6]}}
    extendable_array_keys=(["labels", "subentry"])
    --> result={"labels"{"subentry":[1,2,3,6]}}

    """

    def _merge_fct(a, b):
        if isinstance(b, list):
            return (a or []) + b
        if isinstance(b, dict):
            return (a or {}) | b
        return b

    merged_dict = deepcopy(a)
    for keys_path in include:
        b_value = get_in(keys_path, b)
        if b_value is None:
            # skip the merge if there is no value in b
            continue

        merged_dict = update_in(
            merged_dict, keys_path, lambda x, b_value=b_value: _merge_fct(x, b_value)
        )

    return merged_dict


def get_longest_key_paths(data: dict[str, Any]) -> tuple[list[str], ...]:
    """
    returns: a tuple containing all the paths the keys are taking

    example:
    >>> get_longest_key_paths({
        "a": 3,
        "c": {
            "p": 12,
            "h": {
                "k": 2,
            },
        },
    })
    (
        ["a"],
        ["c", "p"],
        ["c", "h", "k"],
    )
    """

    def _get_parent_keys(
        dict_data: dict[str, Any], parents: Optional[list[str]]
    ) -> list[list[str]]:
        root_parents: list[str] = [] if parents is None else parents

        parents_collection: list[list[str]] = []

        for key, value in dict_data.items():
            if isinstance(value, dict):
                parents_copy = deepcopy(root_parents)
                parents_copy.append(key)
                parents_collection += _get_parent_keys(value, parents_copy)
            else:
                parents_copy = deepcopy(root_parents)
                parents_copy.append(key)
                parents_collection.append(parents_copy)

        if len(dict_data) == 0 and len(root_parents) > 0:
            parents_collection.append(deepcopy(root_parents))

        return parents_collection

    return tuple(_get_parent_keys(data, None))
