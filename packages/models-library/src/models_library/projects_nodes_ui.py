"""
    Models node UI (legacy model, use instead projects.ui.py)
"""

from pydantic import BaseModel, ConfigDict, Field
from pydantic_extra_types.color import Color


class Position(BaseModel):
    x: int = Field(..., description="The x position", examples=[["12"]])
    y: int = Field(..., description="The y position", examples=[["15"]])
    model_config = ConfigDict(extra="forbid")


class Marker(BaseModel):
    color: Color = Field(...)
    model_config = ConfigDict(extra="forbid")
