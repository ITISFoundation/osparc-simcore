from typing import Dict, Optional

from ..domain import project
from ..domain.dag import DAG, DAGBase


class DAGIn(DAGBase):
    workbench: Optional[Dict[str, project.Node]]


class DAGInPath(DAGBase):
    version: str
    name: str
    description: Optional[str]
    contact: Optional[str]
    workbench: Optional[Dict[str, project.Node]]


class DAGOut(DAG):
    pass
