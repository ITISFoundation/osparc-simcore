from typing import Dict, Optional

from models_library.project_nodes import KEY_RE, VERSION_RE, Node
from pydantic import BaseModel, EmailStr, Field, Json


class DAGBase(BaseModel):
    key: str = Field(
        ..., regex=KEY_RE, example="simcore/services/frontend/nodes-group/macros/1"
    )
    version: str = Field(..., regex=VERSION_RE, example="1.0.0")
    name: str
    description: Optional[str]
    contact: Optional[EmailStr]


class DAGAtDB(DAGBase):
    id: int
    workbench: Json[Dict[str, Node]]  # pylint: disable=unsubscriptable-object

    class Config:
        orm_mode = True


class DAGData(DAGAtDB):
    workbench: Optional[Dict[str, Node]]
