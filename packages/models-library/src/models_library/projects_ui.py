"""
    Models Front-end UI
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, validator
from pydantic_extra_types.color import Color

from .projects_nodes_io import NodeID, NodeIDStr
from .projects_nodes_ui import Marker, Position
from .utils.common_validators import empty_str_to_none_pre_validator


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")
    marker: Marker | None = None
    model_config = ConfigDict(extra="forbid")


class _SlideshowRequired(TypedDict):
    position: int


class Slideshow(_SlideshowRequired, total=False):
    instructions: str | None  # Instructions about what to do in this step


class Annotation(BaseModel):
    type: Literal["note", "rect", "text"] = Field(...)
    color: Color = Field(...)
    attributes: dict = Field(..., description="svg attributes")
    model_config = ConfigDict(extra="forbid")


class StudyUI(BaseModel):
    workbench: dict[NodeIDStr, WorkbenchUI] | None = None
    slideshow: dict[NodeIDStr, Slideshow] | None = None
    current_node_id: NodeID | None = Field(default=None, alias="currentNodeId")
    annotations: dict[NodeIDStr, Annotation] | None = None
    model_config = ConfigDict(extra="allow")

    _empty_is_none = validator("*", allow_reuse=True, pre=True)(
        empty_str_to_none_pre_validator
    )
