from typing import TypeAlias

from models_library import projects, projects_nodes_io
from models_library.utils import pydantic_tools_extension
from pydantic import AnyUrl, BaseModel, Field

from .. import api_resources
from . import solvers

StudyID: TypeAlias = projects.ProjectID
NodeName: TypeAlias = str
DownloadLink: TypeAlias = AnyUrl


class Study(BaseModel):
    uid: StudyID
    title: str = pydantic_tools_extension.FieldNotRequired()
    description: str = pydantic_tools_extension.FieldNotRequired()

    @classmethod
    def compose_resource_name(cls, study_key) -> api_resources.RelativeResourceName:
        return api_resources.compose_resource_name("studies", study_key)


class StudyPort(solvers.SolverPort):
    key: projects_nodes_io.NodeID = Field(
        ...,
        description="port identifier name."
        "Correponds to the UUID of the parameter/probe node in the study",
        title="Key name",
    )


class LogLink(BaseModel):
    node_name: NodeName
    download_link: DownloadLink


class JobLogsMap(BaseModel):
    log_links: list[LogLink] = Field(..., description="Array of download links")
