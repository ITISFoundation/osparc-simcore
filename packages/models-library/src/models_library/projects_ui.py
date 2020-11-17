"""
    Models Front-end UI
"""

from typing import Dict, Optional

from pydantic import BaseModel, Extra, Field

from .projects_nodes_io import NodeID, NodeID_AsDictKey
from .projects_nodes_ui import Position


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")

    class Config:
        extra = Extra.forbid


class Slideshow(BaseModel):
    position: int = Field(..., description="Slide's position", examples=["0", "2"])

    class Config:
        extra = Extra.forbid


class StudyUI(BaseModel):
    workbench: Optional[Dict[NodeID_AsDictKey, WorkbenchUI]] = Field(None)
    slideshow: Optional[Dict[NodeID_AsDictKey, Slideshow]] = Field(None)
    current_node_id: Optional[NodeID] = Field(alias="currentNodeId")

    class Config:
        extra = Extra.allow
