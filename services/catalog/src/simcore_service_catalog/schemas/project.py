# From  project-v0.0.1.json
# from __future__ import annotations TODO: ???

# TODO: why pylint error in pydantic???
# pylint: disable=no-name-in-module


import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Field

KEY_RE = r'^(simcore)/(services)(/demodec)?/(comp|dynamic|frontend)(/[^\s]+)+$'
VERSION_RE = r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'

current_dir = Path( sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

class Connection(BaseModel):
    nodeUuid: Optional[str]
    output: Optional[str]

class FilePickerOutput(BaseModel):
    store: Union[str, int] # simcore/datcore
    dataset: Optional[str] #
    path: str #
    label: str # name of the file

InputTypes = Union[int, bool, str, float, Connection, FilePickerOutput]
OutputTypes = Union[int, bool, str, float, FilePickerOutput]


class AccessEnum(str, Enum):
    ReadAndWrite="ReadAndWrite"
    Invisible="Invisible"
    ReadOnly="ReadOnly"


class Position(BaseModel):
    x: int
    y: int


class Node(BaseModel):
    key: str = Field(..., regex=KEY_RE, example="simcore/services/comp/sleeper")
    version: str = Field(..., regex=VERSION_RE, example="6.2.0")
    label: str = Field(...)
    progress: float = Field(0, ge=0, le=100)
    thumbnail: Optional[str]

    inputs: Optional[Dict[str, InputTypes]]
    inputAccess: Optional[Dict[str, AccessEnum]]
    inputNodes: List[str] = []

    outputs: Optional[Dict[str, OutputTypes]] = None
    outputNode: Optional[bool] = Field(None, deprecated=True)
    outputNodes: List[str] = []

    parent: Optional[str] = Field(None, description="Parent's (group-nodes') node ID s.", example="nodeUUid1")

    position: Position = Field(...)


class Project(BaseModel):
    uuid: str
    name: str
    description: str
    prjOwner: EmailStr
    creationDate: str
    lastChangeDate: str
    thumbnail: str
    workbench: Dict[str, Node]
    tags: Optional[List[int]] = []


#with open( current_dir / "project.json", 'wt') as fh:
#    print(Project.schema_json(indent=2), file=fh)
