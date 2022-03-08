from typing import Any, Dict

from models_library.projects import ProjectID
from pydantic import BaseModel, Field, constr, validate_arguments

from .generics import DictKey, DictModel, DictValue, Generic
from .projects_nodes_io import NodeIDStr

SERVICE_NETWORK_RE = r"^[a-zA-Z]([a-zA-Z0-9_-]{0,63})$"

PROJECT_NETWORK_PREFIX = "prj-ntwrk"

DockerNetworkName = constr(regex=SERVICE_NETWORK_RE)
DockerNetworkAlias = constr(regex=SERVICE_NETWORK_RE)


@validate_arguments
def validate_network_name(value: DockerNetworkName) -> DockerNetworkName:
    return value


@validate_arguments
def validate_network_alias(value: DockerNetworkAlias) -> DockerNetworkAlias:
    return value


class BaseModelDict(DictModel, Generic[DictKey, DictValue]):
    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        return super().dict(*args, **kwargs)["__root__"]


class ContainerAliases(BaseModelDict[NodeIDStr, DockerNetworkAlias]):
    ...


class NetworksWithAliases(BaseModelDict[DockerNetworkName, ContainerAliases]):
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

    @classmethod
    def create_empty(cls, project_uuid: ProjectID) -> "ProjectNetworks":
        return cls.parse_obj(dict(project_uuid=project_uuid, networks_with_aliases={}))

    @classmethod
    def create(
        cls, project_uuid: ProjectID, networks_with_aliases: NetworksWithAliases
    ) -> "ProjectNetworks":
        return cls.parse_obj(
            dict(project_uuid=project_uuid, networks_with_aliases=networks_with_aliases)
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
