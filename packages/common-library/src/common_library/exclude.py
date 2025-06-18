from typing import Any, Final


class Unset:
    """Sentinel value to indicate that a parameter is not set."""

    VALUE: "Unset"


unuset: Final = Unset()
Unset.VALUE = Unset()


def is_unset(v: Any) -> bool:
    return isinstance(v, Unset)


def is_set(v: Any) -> bool:
    return not isinstance(v, Unset)


def as_dict_exclude_unset(**params) -> dict[str, Any]:
    """Excludes parameters that are instances of UnSet."""
    return {k: v for k, v in params.items() if not isinstance(v, Unset)}


def as_dict_exclude_none(**params) -> dict[str, Any]:
    """Analogous to `as_dict_exclude_unset` but with None.

    Sometimes None is used as a sentinel value, use this function to exclude it.
    """
    return {k: v for k, v in params.items() if v is not None}
