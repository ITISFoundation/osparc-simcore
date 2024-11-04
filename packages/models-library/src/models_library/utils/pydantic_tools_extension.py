from typing import TypeVar

from pydantic import TypeAdapter, ValidationError

T = TypeVar("T")


def parse_obj_or_none(type_: type[T], obj) -> T | None:
    try:
        return TypeAdapter(type_).validate_python(obj)
    except ValidationError:
        return None
