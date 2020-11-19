"""
    Models node UI (legacy model, use instead projects.ui.py)
"""

from pydantic import BaseModel, Extra, Field

class Position(BaseModel):
    x: int = Field(..., description="The x position", example=["12"])
    y: int = Field(..., description="The y position", example=["15"])

    class Config:
        extra = Extra.forbid
