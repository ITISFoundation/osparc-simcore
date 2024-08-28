"""
    Models node UI (legacy model, use instead projects.ui.py)
"""

from pydantic.v1 import BaseModel, Extra, Field
from pydantic.v1.color import Color


class Position(BaseModel):
    x: int = Field(..., description="The x position", example=["12"])
    y: int = Field(..., description="The y position", example=["15"])

    class Config:
        extra = Extra.forbid


class Marker(BaseModel):
    color: Color = Field(...)

    class Config:
        extra = Extra.forbid
