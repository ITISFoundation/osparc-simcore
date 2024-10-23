from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import PositiveInt


class WidgetType(str, Enum):
    TextArea = "TextArea"
    SelectBox = "SelectBox"


class TextArea(BaseModel):
    min_height: PositiveInt = Field(
        ..., alias="minHeight", description="minimum Height of the textarea"
    )

    model_config = ConfigDict(extra="forbid")


class Structure(BaseModel):
    key: str | bool | float
    label: str

    model_config = ConfigDict(extra="forbid")


class SelectBox(BaseModel):
    structure: list[Structure] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")


class Widget(BaseModel):
    widget_type: WidgetType = Field(
        ..., alias="type", description="type of the property"
    )
    details: TextArea | SelectBox

    model_config = ConfigDict(extra="forbid")
