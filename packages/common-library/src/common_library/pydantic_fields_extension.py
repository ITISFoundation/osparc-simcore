from types import UnionType
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic.fields import FieldInfo

NoneType: type = type(None)


def get_type(info: FieldInfo) -> Any:
    field_type = info.annotation
    if args := get_args(info.annotation):
        field_type = next(a for a in args if a is not NoneType)
    return field_type


def _unwrap_annotation(ann):
    """Peel off Annotated wrappers until reaching the core type."""
    while get_origin(ann) is Annotated:
        ann = get_args(ann)[0]
    return ann


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
