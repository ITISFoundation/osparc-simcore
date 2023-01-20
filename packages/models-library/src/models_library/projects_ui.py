"""
    Models Front-end UI
"""

from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Extra, Field
from pydantic.color import Color

from .projects_nodes_io import NodeID, NodeIDStr
from .projects_nodes_ui import Marker, Position


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")
    marker: Optional[Marker] = None

    class Config:
        extra = Extra.forbid


class _SlideshowRequired(TypedDict):
    position: int


class Slideshow(_SlideshowRequired, total=False):
    instructions: Optional[str]  # "Instructions about what to do in this step"


class Annotation(BaseModel):
    type: Literal["rect", "text"] = Field(...)
    color: Color = Field(...)
    attributes: dict = Field(..., description="svg attributes")

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
    workbench: Optional[dict[NodeIDStr, WorkbenchUI]] = None
    slideshow: Optional[dict[NodeIDStr, Slideshow]] = None
    current_node_id: Optional[NodeID] = Field(None, alias="currentNodeId")
    annotations: Optional[dict[NodeIDStr, Annotation]] = None

    class Config:
        extra = Extra.allow
