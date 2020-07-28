from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class WorkbenchEntryPosition(BaseModel):
    x: int
    y: int


class WorkbenchEntry(BaseModel):
    key: str
    version: str
    label: str
    inputAccess: Optional[Dict[str, str]]
    inputNodes: Dict[str, str]
    inputs: Dict[str, str]
    thumbnail: str
    position: WorkbenchEntryPosition


TypeWorkbench = Dict[str, WorkbenchEntry]


class ProjectUpdate(BaseModel):
    project_id: UUID
    workbench: TypeWorkbench
