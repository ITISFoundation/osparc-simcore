"""
    Models Front-end UI
"""

from typing import Dict, Literal, Optional

from pydantic import BaseModel, Extra, Field
from pydantic.color import Color

from .projects_nodes_io import NodeID, NodeIDStr
from .projects_nodes_ui import Marker, Position


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")
    marker: Optional[Marker] = None

    class Config:
        extra = Extra.forbid


class Slideshow(BaseModel):
    position: int = Field(..., description="Slide's position", examples=["0", "2"])
    instructions: str = Field(
        ...,
        description="Instructions about what to do in this step",
        examples=[
            "This is a **sleeper**",
            "Please, select the config file defined [in this link](asdf)"
        ]
    )

    class Config:
        extra = Extra.forbid


class Annotation(BaseModel):
    type: Literal["rect", "text"] = Field(...)
    color: Color = Field(...)
    attributes: Dict = Field(..., description="svg attributes")

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "examples": [
                {
                    "type": "rect",
                    "color": "#FF0000",
                    "attributes": {"x": 415, "y": 100, "width": 117, "height": 26},
                },
                {
                    "type": "text",
                    "color": "#0000FF",
                    "attributes": {"x": 415, "y": 100, "text": "Hey!"},
                },
            ]
        }


class StudyUI(BaseModel):
    workbench: Optional[Dict[NodeIDStr, WorkbenchUI]] = None
    slideshow: Optional[Dict[NodeIDStr, Slideshow]] = None
    current_node_id: Optional[NodeID] = Field(None, alias="currentNodeId")
    annotations: Optional[Dict[NodeIDStr, Annotation]] = None

    class Config:
        extra = Extra.allow
