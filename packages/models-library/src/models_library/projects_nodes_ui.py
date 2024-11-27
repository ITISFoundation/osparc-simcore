"""
    Models node UI (legacy model, use instead projects.ui.py)
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic_extra_types.color import Color


class Position(BaseModel):
    x: int = Field(..., description="The x position", examples=[["12"]])
    y: int = Field(..., description="The y position", examples=[["15"]])

    model_config = ConfigDict(extra="forbid")


class Marker(BaseModel):
    color: Annotated[Color, PlainSerializer(Color.as_hex), Field(...)]

    model_config = ConfigDict(extra="forbid")
