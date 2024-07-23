""" Helpers for json serialization
    - built-in json-like API
    - implemented using orjson, which  performs better. SEE https://github.com/ijl/orjson?tab=readme-ov-file#performance
"""

from collections.abc import Callable
from typing import Any, Final, NamedTuple

import orjson
from pydantic.json import ENCODERS_BY_TYPE, pydantic_encoder
from pydantic.types import ConstrainedFloat


class SeparatorTuple(NamedTuple):
    item_separator: str
    key_separator: str


# Extends encoders for pydantic_encoder
ENCODERS_BY_TYPE[ConstrainedFloat] = float

_orjson_default_separator: Final = SeparatorTuple(item_separator=",", key_separator=":")


def json_dumps(
    obj: Any,
    *,
    default=pydantic_encoder,
    sort_keys: bool = False,
    indent: int | None = None,
    separators: SeparatorTuple | tuple[str, str] | None = None,
) -> str:
    """json.dumps-like API implemented with orjson.dumps in the core

    NOTE: only separator=(",",":") is supported
    """
    # SEE https://github.com/ijl/orjson?tab=readme-ov-file#serialize
    option = (
        # if a dict has a key of a type other than str it will NOT raise
        orjson.OPT_NON_STR_KEYS
    )
    if indent:
        option |= orjson.OPT_INDENT_2
    if sort_keys:
        option |= orjson.OPT_SORT_KEYS

    if separators is not None and separators != _orjson_default_separator:
        # NOTE1: replacing separators in the result is no only time-consuming but error prone. We had
        # some examples with time-stamps that were corrupted because of this replacement.
        msg = f"Only {_orjson_default_separator} supported, got {separators}"
        raise ValueError(msg)

    # serialize
    result: str = orjson.dumps(obj, default=default, option=option).decode("utf-8")

    return result


json_loads: Callable = orjson.loads


class JsonNamespace:
    """Namespace to use our customized serialization functions for interfaces where the built-in json Api is expected"""

    dumps = json_dumps
    loads = json_loads
