"""
    Models Front-end UI
"""

from typing import Dict, Optional

from pydantic import BaseModel, Extra, Field

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


class StudyUI(BaseModel):
    workbench: Optional[Dict[NodeIDStr, WorkbenchUI]] = Field(None)
    slideshow: Optional[Dict[NodeIDStr, Slideshow]]
    current_node_id: Optional[NodeID] = Field(alias="currentNodeId")

    class Config:
        extra = Extra.allow
