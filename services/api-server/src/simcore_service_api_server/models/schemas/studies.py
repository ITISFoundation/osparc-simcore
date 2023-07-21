from typing import TypeAlias

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.utils.pydantic_tools_extension import FieldNotRequired
from pydantic import BaseModel, Field

from .solvers import SolverPort

StudyID: TypeAlias = ProjectID


# OUTPUT
class Study(BaseModel):  # StudyGet
    uid: StudyID
    title: str = FieldNotRequired()
    description: str = FieldNotRequired()


class StudyPort(SolverPort):
    key: NodeID = Field(
        ...,
        description="port identifier name."
        "Correponds to the UUID of the parameter/probe node in the study",
        title="Key name",
    )
