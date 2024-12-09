from typing import Any


class UnSet:
    VALUE: "UnSet"


UnSet.VALUE = UnSet()


def as_dict_exclude_unset(**params) -> dict[str, Any]:
    return {k: v for k, v in params.items() if not isinstance(v, UnSet)}
