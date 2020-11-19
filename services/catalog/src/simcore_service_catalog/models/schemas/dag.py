from typing import Dict, Optional

from models_library.projects_nodes import Node

from ..domain.dag import DAGBase, DAGData


class DAGIn(DAGBase):
    workbench: Optional[Dict[str, Node]]


class DAGInPath(DAGBase):
    version: str
    name: str
    description: Optional[str]
    contact: Optional[str]
    workbench: Optional[Dict[str, Node]]


class DAGOut(DAGData):
    pass
