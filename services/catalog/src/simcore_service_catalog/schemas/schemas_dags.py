from typing import Dict, Optional

# TODO: why pylint error in pydantic???
# pylint: disable=no-name-in-module
from pydantic import BaseModel, EmailStr, Field, Json

from . import project
from .project import KEY_RE, VERSION_RE

#   const outputNode = this.getOutputNode();
#   const nodeKey = "simcore/services/frontend/nodes-group/macros/" + outputNode.getNodeId();
#   const version = "1.0.0";
#   const nodesGroupService = osparc.utils.Services.getNodesGroup();
#   nodesGroupService["key"] = nodeKey;
#   nodesGroupService["version"] = version;
#   nodesGroupService["name"] = this.__groupName.getValue();
#   nodesGroupService["description"] = this.__groupDesc.getValue();
#   nodesGroupService["contact"] = osparc.auth.Data.getInstance().getEmail();
#   nodesGroupService["workbench"] = workbench;


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
