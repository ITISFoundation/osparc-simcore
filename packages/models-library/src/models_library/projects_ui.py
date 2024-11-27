"""
    Models Front-end UI
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator
from pydantic_extra_types.color import Color
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

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
    color: Annotated[Color, PlainSerializer(Color.as_hex), Field(...)]
    attributes: dict = Field(..., description="svg attributes")
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
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
                        "text": "ToDo",
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
        },
    )


class StudyUI(BaseModel):
    workbench: dict[NodeIDStr, WorkbenchUI] | None = None
    slideshow: dict[NodeIDStr, Slideshow] | None = None
    current_node_id: NodeID | None = Field(default=None, alias="currentNodeId")
    annotations: dict[NodeIDStr, Annotation] | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    _empty_is_none = field_validator("*", mode="before")(
        empty_str_to_none_pre_validator
    )
