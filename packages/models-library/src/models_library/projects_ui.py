from typing import Dict, Optional

from pydantic import BaseModel, Extra, Field, constr
from .basic_regex import UUID_RE
from .project_nodes import Node, Position
NodeID = constr(regex=UUID_RE)

# Pydantic does not support exporting a jsonschema with Dict keys being something else than a str
# this is a regex for having uuids of type: 8-4-4-4-12 digits
_NodeIDForDict = constr(
    regex=r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)
Workbench = Dict[_NodeIDForDict, Node]




class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")

    class Config:
        extra = Extra.forbid


class Slideshow(BaseModel):
    position: int = Field(..., description="Slide's position", example=["0", "2"])

    class Config:
        extra = Extra.forbid



class StudyUI(BaseModel):
    workbench: Optional[Dict[_NodeIDForDict, WorkbenchUI]] = Field(None)
    slideshow: Optional[Dict[_NodeIDForDict, Slideshow]] = Field(None)
    current_node_id: Optional[NodeID] = Field(alias="currentNodeId")

    class Config:
        extra = Extra.allow
