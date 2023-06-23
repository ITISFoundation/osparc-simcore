"""
    Models Front-end UI
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, Extra, Field, validator
from pydantic.color import Color

from .projects_nodes_io import NodeID, NodeIDStr
from .projects_nodes_ui import Marker, Position
from .utils.common_validators import empty_str_to_none


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")
    marker: Marker | None = None

    class Config:
        extra = Extra.forbid


class _SlideshowRequired(TypedDict):
    position: int


class Slideshow(_SlideshowRequired, total=False):
    instructions: str | None  # Instructions about what to do in this step


class Annotation(BaseModel):
    type: Literal["note", "rect", "text"] = Field(...)
    color: Color = Field(...)
    attributes: dict = Field(..., description="svg attributes")

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "examples": [
                {
                    "type": "note",
                    "color": "#FFFF00",
                    "attributes": {
                        "x": 415,
                        "y": 100,
                        "width": 117,
                        "height": 26,
                        "destinataryGid": 4,
                        "text": "ToDo"
                    },
                },
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
    workbench: dict[NodeIDStr, WorkbenchUI] | None = None
    slideshow: dict[NodeIDStr, Slideshow] | None = None
    current_node_id: NodeID | None = Field(default=None, alias="currentNodeId")
    annotations: dict[NodeIDStr, Annotation] | None = None

    class Config:
        extra = Extra.allow

    _empty_is_none = validator("*", allow_reuse=True, pre=True)(empty_str_to_none)
