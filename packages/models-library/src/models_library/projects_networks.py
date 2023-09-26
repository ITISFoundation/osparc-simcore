import re
from typing import Any, ClassVar, Final

from pydantic import BaseModel, ConstrainedStr, Field

from .generics import DictModel
from .projects import ProjectID
from .projects_nodes_io import NodeIDStr

SERVICE_NETWORK_RE: Final[re.Pattern] = re.compile(r"^[a-zA-Z]([a-zA-Z0-9_-]{0,63})$")

PROJECT_NETWORK_PREFIX: Final[str] = "prj-ntwrk"


class DockerNetworkName(ConstrainedStr):
    regex = SERVICE_NETWORK_RE


class DockerNetworkAlias(ConstrainedStr):
    regex = SERVICE_NETWORK_RE


class ContainerAliases(DictModel[NodeIDStr, DockerNetworkAlias]):
    ...


class NetworksWithAliases(DictModel[DockerNetworkName, ContainerAliases]):
    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "network_one": {
                        "00000000-0000-0000-0000-000000000001": "an_alias_for_container_1_in_network_one",
                        "00000000-0000-0000-0000-000000000002": "some_other_alias_for_container_2_in_network_one",
                    }
                },
            ]
        }


class ProjectsNetworks(BaseModel):
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
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "project_uuid": "ec5cdfea-f24e-4aa1-83b8-6dccfdc8cf4d",
                "networks_with_aliases": {
                    "network_one": {
                        "00000000-0000-0000-0000-000000000001": "an_alias_for_container_1_in_network_one",
                        "00000000-0000-0000-0000-000000000002": "some_other_alias_for_container_2_in_network_one",
                    }
                },
            }
        }
