from typing import TypeVar

from pydantic import ValidationError
from pydantic.tools import parse_obj_as

T = TypeVar("T")


def parse_obj_or_none(type_: type[T], obj) -> T | None:
    try:
        return parse_obj_as(type_, obj)
    except ValidationError:
        return None
