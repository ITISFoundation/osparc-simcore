from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic_extra_types.color import Color


class Position(BaseModel):
    x: int = Field(..., description="The x position", examples=[["12"]])
    y: int = Field(..., description="The y position", examples=[["15"]])

    model_config = ConfigDict(extra="forbid")


class Marker(BaseModel):
    color: Annotated[Color, PlainSerializer(Color.as_hex), Field(...)]

    model_config = ConfigDict(extra="forbid")


class NodeUI(BaseModel):
    position: Annotated[
        Position,
        Field(description="The node position in the workbench"),
    ]
    marker: Marker | None = None

    model_config = ConfigDict(extra="forbid")
