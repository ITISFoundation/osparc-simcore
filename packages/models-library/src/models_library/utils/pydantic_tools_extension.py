from typing import Final, TypeVar

from pydantic import TypeAdapter, ValidationError

T = TypeVar("T")


def parse_obj_or_none(type_: type[T], obj) -> T | None:
    try:
        return TypeAdapter(type_).validate_python(obj)
    except ValidationError:
        return None


#
# NOTE: Helper to define non-nullable optional fields
# SEE details in test/test_utils_pydantic_tools_extension.py
#
# Two usage styles:
#
# class Model(BaseModel):
#     other: Field(NOT_REQUIRED, description="alternative")
#
NOT_REQUIRED: Final = None
