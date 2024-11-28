""" Helpers for json serialization
    - built-in json-like API
    - implemented using orjson, which  performs better. SEE https://github.com/ijl/orjson?tab=readme-ov-file#performance
"""

import datetime
from collections import deque
from collections.abc import Callable
from decimal import Decimal
from enum import Enum
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from pathlib import Path
from re import Pattern
from types import GeneratorType
from typing import Any, Final, NamedTuple
from uuid import UUID

import orjson
from pydantic import AnyHttpUrl, AnyUrl, HttpUrl, NameEmail, SecretBytes, SecretStr
from pydantic_core import Url
from pydantic_extra_types.color import Color


class SeparatorTuple(NamedTuple):
    item_separator: str
    key_separator: str


_orjson_default_separator: Final = SeparatorTuple(item_separator=",", key_separator=":")


def isoformat(o: datetime.date | datetime.time) -> str:
    return o.isoformat()


def decimal_encoder(dec_value: Decimal) -> int | float:
    """
    Encodes a Decimal as int of there's no exponent, otherwise float

    This is useful when we use ConstrainedDecimal to represent Numeric(x,0)
    where a integer (but not int typed) is used. Encoding this as a float
    results in failed round-tripping between encode and parse.
    Our Id type is a prime example of this.

    >>> decimal_encoder(Decimal("1.0"))
    1.0

    >>> decimal_encoder(Decimal("1"))
    1
    """
    if dec_value.as_tuple().exponent >= 0:  # type: ignore[operator]
        return int(dec_value)

    return float(dec_value)


ENCODERS_BY_TYPE: dict[type[Any], Callable[[Any], Any]] = {
    AnyHttpUrl: str,
    AnyUrl: str,
    bytes: lambda o: o.decode(),
    Color: str,
    datetime.date: isoformat,
    datetime.datetime: isoformat,
    datetime.time: isoformat,
    datetime.timedelta: lambda td: td.total_seconds(),
    Decimal: decimal_encoder,
    Enum: lambda o: o.value,
    frozenset: list,
    deque: list,
    GeneratorType: list,
    HttpUrl: str,
    IPv4Address: str,
    IPv4Interface: str,
    IPv4Network: str,
    IPv6Address: str,
    IPv6Interface: str,
    IPv6Network: str,
    NameEmail: str,
    Path: str,
    Pattern: lambda o: o.pattern,
    SecretBytes: str,
    SecretStr: str,
    set: list,
    Url: str,
    UUID: str,
}


def pydantic_encoder(obj: Any) -> Any:
    from dataclasses import asdict, is_dataclass

    from pydantic.main import BaseModel

    if isinstance(obj, BaseModel):
        return obj.model_dump()

    if is_dataclass(obj):
        assert not isinstance(obj, type)  # nosec
        return asdict(obj)

    # Check the class type and its superclasses for a matching encoder
    for base in obj.__class__.__mro__[:-1]:
        try:
            encoder = ENCODERS_BY_TYPE[base]
        except KeyError:
            continue
        return encoder(obj)

    # We have exited the for loop without finding a suitable encoder
    msg = f"Object of type '{obj.__class__.__name__}' is not JSON serializable"
    raise TypeError(msg)


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
