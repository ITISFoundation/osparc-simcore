from enum import Enum
from typing import Union

from pydantic import BaseModel, Extra, Field
from pydantic.types import PositiveInt


class WidgetType(str, Enum):
    TextArea = "TextArea"
    SelectBox = "SelectBox"


# class PositiveIntWithExclusiveMinimumRemoved(PositiveInt):
#     # As we are trying to match this Pydantic model to a historical json schema "project-v0.0.1" we need to remove this
#     # Pydantic does not support exclusiveMinimum boolean https://github.com/pydantic/pydantic/issues/4108
#     @classmethod
#     def __modify_schema__(cls, field_schema):
#         field_schema.pop("exclusiveMinimum", None)


class TextArea(BaseModel):
    min_height: PositiveInt = Field(
        ..., alias="minHeight", description="minimum Height of the textarea"
    )

    class Config:
        extra = Extra.forbid


class Structure(BaseModel):
    key: Union[str, bool, float]
    label: str

    class Config:
        extra = Extra.forbid


class SelectBox(BaseModel):
    structure: list[Structure] = Field(..., min_items=1)

    class Config:
        extra = Extra.forbid


class Widget(BaseModel):
    widget_type: WidgetType = Field(
        ..., alias="type", description="type of the property"
    )
    details: Union[TextArea, SelectBox]

    class Config:
        extra = Extra.forbid
