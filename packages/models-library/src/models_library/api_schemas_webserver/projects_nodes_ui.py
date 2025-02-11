from typing import Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic_extra_types.color import Color

from ..projects_nodes_layout import Position

PositionUI: TypeAlias = Position


class MarkerUI(BaseModel):
    color: Annotated[Color, PlainSerializer(Color.as_hex), Field(...)]

    model_config = ConfigDict(extra="forbid")
