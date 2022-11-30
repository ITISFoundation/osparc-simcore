from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import Field

from .solvers import SolverPort

StudyID = ProjectID


class StudyPort(SolverPort):
    key: NodeID = Field(
        ...,
        description="port identifier name",
        title="Key name",
    )
