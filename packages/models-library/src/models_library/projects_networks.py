import re
from typing import Final

from pydantic import BaseModel, ConfigDict, ConstrainedStr, Field

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
    model_config = ConfigDict()


class ProjectsNetworks(BaseModel):
    project_uuid: ProjectID = Field(..., description="project reference")
    networks_with_aliases: NetworksWithAliases = Field(
        ...,
        description=(
            "Networks which connect nodes from the project. Each node "
            "is given a user defined alias by which it is identified on the network."
        ),
    )
    model_config = ConfigDict(from_attributes=True)
