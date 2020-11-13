from typing import Dict, Optional

from pydantic import BaseModel, Extra, Field, constr
from .basic_regex import UUID_RE

NodeID = constr(regex=UUID_RE)


class Position(BaseModel):
    x: int = Field(..., description="The x position", example=["12"])
    y: int = Field(..., description="The y position", example=["15"])

    class Config:
        extra = Extra.forbid


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")

    class Config:
        extra = Extra.forbid


class Slideshow(BaseModel):
    position: int = Field(..., description="Slide's position", example=["0", "2"])

    class Config:
        extra = Extra.forbid


class StudyUI(BaseModel):
    workbench: Optional[Dict[NodeID, WorkbenchUI]] = Field(None)
    slideshow: Optional[Dict[NodeID, Slideshow]] = Field(None)
