from typing import Dict
from uuid import UUID

from pydantic import BaseModel


class WorkbenchEntryPosition(BaseModel):
    x: int
    y: int


class WorkbenchEntry(BaseModel):
    key: str
    version: str
    label: str
    inputAccess: Dict[str, str]
    inputNodes: Dict[str, str]
    inputs: Dict[str, str]
    thumbnail: str
    position: WorkbenchEntryPosition


TypeWorkbench = Dict[UUID, WorkbenchEntry]
