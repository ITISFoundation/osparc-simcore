from copy import deepcopy
from typing import Any

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
        assert b_value is not None  # nosec
        merged_dict = update_in(
            merged_dict, keys_path, lambda x, b_value=b_value: _merge_fct(x, b_value)
        )

    return merged_dict
