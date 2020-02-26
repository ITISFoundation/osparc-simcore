from typing import Dict, Optional

# TODO: why pylint error in pydantic???
# pylint: disable=no-name-in-module
from pydantic import BaseModel, EmailStr, Field, Json

from . import project
from .project import KEY_RE, VERSION_RE


class DAGBase(BaseModel):
    key: str = Field(
        ..., regex=KEY_RE, example="simcore/services/frontend/nodes-group/macros/1"
    )
    version: str = Field(..., regex=VERSION_RE, example="1.0.0")
    name: str
    description: Optional[str]
    contact: Optional[EmailStr]


class DAGIn(DAGBase):
    workbench: Optional[Dict[str, project.Node]]


class DAGInPath(DAGBase):
    version: str
    name: str
    description: Optional[str]
    contact: Optional[str]
    workbench: Optional[Dict[str, project.Node]]


class DAGAtDB(DAGBase):
    id: int
    workbench: Json[Dict[str, project.Node]]

    class Config:
        orm_mode = True


class DAGOut(DAGAtDB):
    workbench: Optional[Dict[str, project.Node]]
