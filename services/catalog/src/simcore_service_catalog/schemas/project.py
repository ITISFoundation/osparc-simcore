# From  project-v0.0.1.json
# from __future__ import annotations TODO: ???

# TODO: why pylint error in pydantic???
# pylint: disable=no-name-in-module


from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, EmailStr

KEY_RE = r'^(simcore)/(services)(/demodec)?/(comp|dynamic|frontend)(/[^\s]+)+$'
VERSION_RE = r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'


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
    key: str = Field(..., regex=KEY_RE, example="simcore/services/comp/sleeper")
    version: str = Field(..., regex=VERSION_RE, example="6.2.0")
    label: str
    progress: float
    thumbnail: Optional[str]
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
    prjOwner: Optional[EmailStr]
    creationDate: str
    lastChangeDate: str
    thumbnail: str
    workbench: Dict[str, Node]
