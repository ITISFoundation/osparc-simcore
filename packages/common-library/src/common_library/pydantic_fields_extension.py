from types import UnionType
from typing import Annotated, Any, Literal, TypeAliasType, Union, get_args, get_origin

from pydantic.fields import FieldInfo

NoneType: type = type(None)


def _unwrap_annotation(ann):
    """Peel off Annotated wrappers and PEP 695 type aliases (`type X = ...`) until reaching the core type."""
    while True:
        if get_origin(ann) is Annotated:
            ann = get_args(ann)[0]
        elif isinstance(ann, TypeAliasType):
            ann = ann.__value__
        else:
            return ann


def get_type(info: FieldInfo) -> Any:
    field_type = _unwrap_annotation(info.annotation)
    if args := get_args(field_type):
        field_type = next(a for a in args if a is not NoneType)
    return field_type


def is_literal(info: FieldInfo) -> bool:
    ann = _unwrap_annotation(info.annotation)
    return get_origin(ann) is Literal


def is_nullable(info: FieldInfo) -> bool:
    """Checks whether a field allows None as a value."""
    ann = _unwrap_annotation(info.annotation)
    origin = get_origin(ann)  # X | None or Optional[X] will return Union

    if origin in (Union, UnionType):
        return any(arg is NoneType or arg is Any for arg in get_args(ann))

    return ann is NoneType or ann is Any
