from models_library.projects import ProjectID
from pydantic import BaseModel, Field, constr

from .generics import DictModel
from .projects_nodes_io import NodeIDStr

SERVICE_NETWORK_RE = r"^[a-zA-Z]([a-zA-Z0-9_-]{0,63})$"

PROJECT_NETWORK_PREFIX = "prj-ntwrk"

DockerNetworkName = constr(regex=SERVICE_NETWORK_RE)
DockerNetworkAlias = constr(regex=SERVICE_NETWORK_RE)


class ContainerAliases(DictModel[NodeIDStr, DockerNetworkAlias]):
    ...


class NetworksWithAliases(DictModel[DockerNetworkName, ContainerAliases]):
    class Config:
        schema_extra = {
            "examples": [
                {"nSetwork_name12-s": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
                {"C": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
                {"shr-ntwrk_5c743ad2-8fdb-11ec-bb3a-02420a000008_default": {}},
            ]
        }


class ProjectNetworks(BaseModel):
    project_uuid: ProjectID = Field(..., description="project reference")
    networks_with_aliases: NetworksWithAliases = Field(
        ...,
        description=(
            "Networks which connect nodes from the project. Each node "
            "is given a user defined alias by which it is identified on the network."
        ),
    )

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "project_uuid": "ec5cdfea-f24e-4aa1-83b8-6dccfdc8cf4d",
                "networks_with_aliases": {
                    "nSetwork_name12-s": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}
                },
            }
        }
