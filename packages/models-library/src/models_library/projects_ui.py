"""
    Models Front-end UI
"""

from typing import Dict, Optional

from pydantic import BaseModel, Extra, Field, Literal
from pydantic.color import Color

from .projects_nodes_io import NodeID, NodeIDStr
from .projects_nodes_ui import Position


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")

    class Config:
        extra = Extra.forbid


class Slideshow(BaseModel):
    position: int = Field(..., description="Slide's position", examples=["0", "2"])

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
    workbench: Optional[Dict[NodeIDStr, WorkbenchUI]] = Field(None)
    slideshow: Optional[Dict[NodeIDStr, Slideshow]]
    current_node_id: Optional[NodeID] = Field(alias="currentNodeId")
    annotations: Optional[Dict[NodeIDStr, Annotation]]

    class Config:
        extra = Extra.allow
