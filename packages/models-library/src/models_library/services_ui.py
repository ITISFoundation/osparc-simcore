from enum import Enum

from pydantic import BaseModel, Extra, Field
from pydantic.types import PositiveInt


class WidgetType(str, Enum):
    TextArea = "TextArea"
    SelectBox = "SelectBox"


class TextArea(BaseModel):
    min_height: PositiveInt = Field(
        ..., alias="minHeight", description="minimum Height of the textarea"
    )

    class Config:
        extra = Extra.forbid


class Structure(BaseModel):
    key: str | bool | float
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
    details: TextArea | SelectBox

    class Config:
        extra = Extra.forbid
