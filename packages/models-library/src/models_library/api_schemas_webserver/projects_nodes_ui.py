from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic_extra_types.color import Color

from ..projects_nodes_layout import Position

type PositionUI = Position


class MarkerUI(BaseModel):
    color: Annotated[Color, PlainSerializer(Color.as_hex), Field(...)]

    model_config = ConfigDict(extra="forbid")


class NodeUI(BaseModel):
    position: PositionUI
    marker: MarkerUI | None = None

    model_config = ConfigDict(extra="forbid")


class NodeUIPatch(BaseModel):
    position: Annotated[
        PositionUI | None,
        Field(description="The node position in the workbench"),
    ] = None
    marker: MarkerUI | None = None

    model_config = ConfigDict(extra="forbid")
