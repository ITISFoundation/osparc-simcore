""" Helpers for json serialization
    - built-in json-like API
    - implemented using orjson, which  performs better. SEE https://github.com/ijl/orjson?tab=readme-ov-file#performance
"""

from typing import Any, Final, NamedTuple

import orjson
from pydantic.json import pydantic_encoder


class SeparatorTuple(NamedTuple):
    item_separator: str
    key_separator: str


_orjson_default_separator: Final = SeparatorTuple(item_separator=",", key_separator=":")


def orjson_dumps(
    obj: Any,
    *,
    default=pydantic_encoder,
    sort_keys: bool = False,
    indent: int | None = None,
    separators: SeparatorTuple | tuple[str, str] | None = None,
):
    """json.dumps-like API implemented with orjson.dumps in the core"""
    # SEE https://github.com/ijl/orjson?tab=readme-ov-file#serialize
    option = (
        # if a dict has a key of a type other than str it will NOT raise
        orjson.OPT_NON_STR_KEYS
    )
    if indent:
        option |= orjson.OPT_INDENT_2
    if sort_keys:
        option |= orjson.OPT_SORT_KEYS

    if separators is not None:
        separators = SeparatorTuple(*separators)

    # serialize
    result: str = orjson.dumps(obj, default=default, option=option).decode("utf-8")

    # post-process
    if separators is not None and separators != _orjson_default_separator:
        assert isinstance(separators, SeparatorTuple)  # nosec
        result = result.replace(
            _orjson_default_separator.key_separator,
            separators.key_separator,
        ).replace(
            _orjson_default_separator.item_separator,
            separators.item_separator,
        )

    return result


orjson_loads = orjson.loads


class OrJsonNamespace:
    """Namespace to use orjson as a replacement for interfaces where the built-in json namespace is expected"""

    dumps = orjson_dumps
    loads = orjson_loads
