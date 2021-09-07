from datetime import datetime
from typing import Any, Dict, Optional, Union
from uuid import UUID

from models_library.basic_types import SHA1Str
from models_library.projects_nodes import Node
from pydantic import BaseModel, PositiveInt, StrictBool, StrictFloat, StrictInt

BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]


class Checkpoint(BaseModel):
    id: PositiveInt
    checksum: SHA1Str

    tag: str
    message: str

    parent: PositiveInt
    created_at: datetime


# API models ---------------


class CheckpointNew(BaseModel):
    tag: str
    message: Optional[str] = None
    new_branch: Optional[str] = None


class CheckpointAnnotations(BaseModel):
    tag: Optional[str] = None
    message: Optional[str] = None


class WorkbenchView(BaseModel):
    """A view (i.e. read-only and visual) of the project's workbench"""

    workbench: Dict[UUID, Node] = {}
    ui: Dict[UUID, Any] = {}
