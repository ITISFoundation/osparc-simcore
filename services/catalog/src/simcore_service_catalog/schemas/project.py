# From  project-v0.0.1.json
# from __future__ import annotations TODO: ???
from enum import Enum

from typing import Any, Dict, Optional, List

from pydantic import BaseModel

class AccessEnum(Enum):
    ReadAndWrite="ReadAndWrite"
    Invisible="Invisible"
    ReadOnly="ReadOnly"


class Input(BaseModel):
    pass

class Output(BaseModel):
    pass

class Position(BaseModel):
    x: int
    y: int


class Node(BaseModel):
    key: str
    version: str
    label: str
    progress: float
    thumbnail: str
    inputs: Dict[str, Input]
    inputAccess: Dict[str, AccessEnum]
    inputNodes: List[str]
    outputs: Dict[str, Output]
    # outputNodes:
    parent: str
    position: Position


class Project(BaseModel):
    uuid: str
    name: str
    description: str
    prjOwner: str
    creationDate: str
    lastChangeDate: str
    thumbnail: str
    workbench: Dict[str, Node]
