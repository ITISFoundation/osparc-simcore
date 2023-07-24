from ...projects_nodes import Node
from ..domain.dag import DAGBase, DAGData


class DAGIn(DAGBase):
    workbench: dict[str, Node] | None


class DAGInPath(DAGBase):
    version: str
    name: str
    description: str | None
    contact: str | None
    workbench: dict[str, Node] | None


class DAGOut(DAGData):
    pass
