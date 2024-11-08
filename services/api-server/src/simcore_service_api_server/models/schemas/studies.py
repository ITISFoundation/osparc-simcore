from typing import Annotated, TypeAlias

from models_library import projects, projects_nodes_io
from pydantic import AnyUrl, BaseModel, ConfigDict, Field, StringConstraints

from .. import api_resources
from . import solvers

StudyID: TypeAlias = projects.ProjectID
NodeName: TypeAlias = str
DownloadLink: TypeAlias = AnyUrl


class Study(BaseModel):
    uid: StudyID
    title: str | None = None
    description: str | None = None

    @classmethod
    def compose_resource_name(cls, study_key) -> api_resources.RelativeResourceName:
        return api_resources.compose_resource_name("studies", study_key)


class StudyPort(solvers.SolverPort):
    key: projects_nodes_io.NodeID = Field(  # type: ignore[assignment]
        ...,
        description="port identifier name."
        "Correponds to the UUID of the parameter/probe node in the study",
        title="Key name",
    )
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "key": "f763658f-a89a-4a90-ace4-c44631290f12",
                "kind": "input",
                "content_schema": {
                    "title": "Sleep interval",
                    "type": "integer",
                    "x_unit": "second",
                    "minimum": 0,
                    "maximum": 5,
                },
            }
        },
    )


class LogLink(BaseModel):
    node_name: NodeName
    download_link: Annotated[DownloadLink, StringConstraints(max_length=65536)]


class JobLogsMap(BaseModel):
    log_links: list[LogLink] = Field(..., description="Array of download links")
