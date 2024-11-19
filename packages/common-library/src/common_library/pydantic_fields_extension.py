from types import UnionType
from typing import Any, Literal, get_args, get_origin

from pydantic.fields import FieldInfo


def get_type(info: FieldInfo) -> Any:
    field_type = info.annotation
    if args := get_args(info.annotation):
        field_type = next(a for a in args if a is not type(None))
    return field_type


def is_literal(info: FieldInfo) -> bool:
    return get_origin(info.annotation) is Literal


def is_nullable(info: FieldInfo) -> bool:
    origin = get_origin(info.annotation)  # X | None or Optional[X] will return Union
    if origin is UnionType:
        return any(x in get_args(info.annotation) for x in (type(None), Any))
    return False
