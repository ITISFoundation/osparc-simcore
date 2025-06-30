"""
Models Front-end UI
"""

from typing import Annotated, Literal, NotRequired

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PlainSerializer,
    field_validator,
)
from pydantic.config import JsonDict
from pydantic_extra_types.color import Color
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from ..projects_nodes_io import NodeID, NodeIDStr
from ..utils.common_validators import empty_str_to_none_pre_validator
from ._base import OutputSchema
from .projects_nodes_ui import MarkerUI, PositionUI


class WorkbenchUI(BaseModel):
    position: Annotated[
        PositionUI,
        Field(description="The node position in the workbench"),
    ]
    marker: MarkerUI | None = None

    model_config = ConfigDict(extra="forbid")


class SlideshowUI(TypedDict):
    position: int
    instructions: NotRequired[str | None]  # Instructions about what to do in this step


class AnnotationUI(BaseModel):
    type: Literal["note", "rect", "text", "conversation"]
    color: Annotated[Color, PlainSerializer(Color.as_hex)]
    attributes: Annotated[dict, Field(description="svg attributes")]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
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
                    {
                        "type": "conversation",
                        "attributes": {
                            "x": 415,
                            "y": 100,
                            "conversationId": 2,
                        },
                    },
                ]
            },
        )

    model_config = ConfigDict(
        extra="forbid", json_schema_extra=_update_json_schema_extra
    )


class StudyUI(OutputSchema):
    # Model fully controlled by the UI and stored under `projects.ui`
    icon: HttpUrl | None = None

    workbench: dict[NodeIDStr, WorkbenchUI] | None = None
    slideshow: dict[NodeIDStr, SlideshowUI] | None = None
    current_node_id: NodeID | None = None
    annotations: dict[NodeIDStr, AnnotationUI] | None = None
    template_type: Literal["hypertool"] | None = None

    _empty_is_none = field_validator("*", mode="before")(
        empty_str_to_none_pre_validator
    )

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "workbench": {
                            "801407c9-abb1-400d-ac49-35b0b2334a34": {
                                "position": {"x": 250, "y": 100}
                            }
                        }
                    },
                    {
                        "icon": "https://cdn-icons-png.flaticon.com/512/25/25231.png",
                        "mode": "app",
                        "slideshow": {
                            "4b3345e5-861f-47b0-8b52-a4508449be79": {
                                "position": 1,
                                "instructions": None,
                            },
                            "eaeee3dc-9ae1-4bf6-827e-798fd7cad848": {
                                "position": 0,
                                "instructions": None,
                            },
                        },
                        "workbench": {
                            "4b3345e5-861f-47b0-8b52-a4508449be79": {
                                "position": {"x": 460, "y": 260}
                            },
                            "eaeee3dc-9ae1-4bf6-827e-798fd7cad848": {
                                "position": {"x": 220, "y": 600}
                            },
                        },
                        "annotations": {
                            "4375ae62-76ce-42a4-9cea-608a2ba74762": {
                                "type": "rect",
                                "color": "#650cff",
                                "attributes": {
                                    "x": 79,
                                    "y": 194,
                                    "width": "320",
                                    "height": "364",
                                },
                            },
                            "52567518-cedc-47e0-ad7f-6989fb8c5649": {
                                "type": "note",
                                "color": "#ffff01",
                                "attributes": {
                                    "x": 151,
                                    "y": 376,
                                    "text": "ll",
                                    "recipientGid": None,
                                },
                            },
                            "764a17c8-36d7-4865-a5cb-db9b4f82ce80": {
                                "type": "note",
                                "color": "#650cff",
                                "attributes": {
                                    "x": 169,
                                    "y": 19,
                                    "text": "yeah m",
                                    "recipientGid": 20630,
                                },
                            },
                            "cf94f068-259c-4192-89f9-b2a56d51249c": {
                                "type": "text",
                                "color": "#e9aeab",
                                "attributes": {
                                    "x": 119,
                                    "y": 223,
                                    "text": "pppoo",
                                    "color": "#E9AEAB",
                                    "fontSize": 12,
                                },
                            },
                            "cf94f068-259c-4192-89f9-b2a56d51249d": {
                                "type": "conversation",
                                "attributes": {
                                    "x": 119,
                                    "y": 223,
                                    "conversation": 2,
                                },
                            },
                        },
                        "current_node_id": "4b3345e5-861f-47b0-8b52-a4508449be79",
                        "template_type": "hypertool",
                    },
                ]
            }
        )

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        json_schema_extra=_update_json_schema_extra,
    )
