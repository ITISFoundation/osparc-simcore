import typing

import pydantic
from models_library import projects, projects_nodes_io
from models_library.utils import pydantic_tools_extension

from .. import api_resources
from . import solvers

StudyID: typing.TypeAlias = projects.ProjectID


class Study(pydantic.BaseModel):
    uid: StudyID
    title: str = pydantic_tools_extension.FieldNotRequired()
    description: str = pydantic_tools_extension.FieldNotRequired()

    @classmethod
    def compose_resource_name(cls, study_key) -> api_resources.RelativeResourceName:
        return api_resources.compose_resource_name("studies", study_key)


class StudyPort(solvers.SolverPort):
    key: projects_nodes_io.NodeID = pydantic.Field(
        ...,
        description="port identifier name."
        "Correponds to the UUID of the parameter/probe node in the study",
        title="Key name",
    )
