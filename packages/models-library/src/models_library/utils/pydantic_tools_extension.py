import functools
from typing import Final, TypeVar

from pydantic import Field, ValidationError
from pydantic.tools import parse_obj_as

T = TypeVar("T")


def parse_obj_or_none(type_: type[T], obj) -> T | None:
    try:
        return parse_obj_as(type_, obj)
    except ValidationError:
        return None


#
# NOTE: Helper to define non-nullable optional fields
# SEE details in test/test_utils_pydantic_tools_extension.py
#
# Two usage styles:
#
# class Model(BaseModel):
#     value: FieldNotRequired(description="some optional field")
#     other: Field(NOT_REQUIRED, description="alternative")
#
NOT_REQUIRED: Final = None
FieldNotRequired = functools.partial(Field, default=NOT_REQUIRED)
