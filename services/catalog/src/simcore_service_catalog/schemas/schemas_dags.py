from typing import Dict, Optional

from pydantic import BaseModel, Json ## pylint: disable=no-name-in-module
# TODO: why?

from . import project

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
    key: str=""
    version: str=""

    name: str=""
    description: str=""
    contact: str=""


class DAGIn(DAGBase):
    workbench: Optional[Dict[str, project.Node]]

class DAGOut(DAGIn):
    pass

class DAG(DAGIn):
    pass


class DAGAtDB(DAGBase):
    workbench: Json[Dict[str, project.Node]]

    class Config:
        orm_mode = True
