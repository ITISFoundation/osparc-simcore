from typing import TypeVar

from pydantic import ValidationError
from pydantic.tools import parse_obj_as

T = TypeVar("T")


def parse_obj_or_none(type_: type[T], obj) -> T | None:
    """Same as pydantic's parse_obj_as but returns None if fails

    WARNING: Use mainly to assert 'obj' is a 'type_'
    E.g.
        assert parse_obj_or_none(list[OneType | OtherType], obj)

    """
    try:
        return parse_obj_as(type_, obj)
    except ValidationError:
        return None
