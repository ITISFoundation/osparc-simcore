from ipaddress import IPv4Address
from typing import Any, Mapping, Union

from pydantic import BaseModel, ByteSize, Field, PositiveFloat, parse_obj_as

Hostname = str
ResourceName = str
ResourceType = Union[int, float]


class NodeResources(BaseModel):
    memory: ByteSize
    cpus: PositiveFloat
    others: dict[ResourceName, ResourceType] = Field(default_factory=dict)


class NodeInformation(BaseModel):
    docker_node_id: str
    ip: IPv4Address
    resources: NodeResources


ClusterInformation = dict[Hostname, NodeInformation]


def cluster_information_from_docker_nodes(
    nodes_list: list[Mapping[str, Any]]
) -> ClusterInformation:
    return parse_obj_as(
        ClusterInformation,
        {
            node["Description"]["Hostname"]: {
                "docker_node_id": node["ID"],
                "ip": node["Status"]["Addr"],
                "resources": {
                    "memory": node["Description"]["Resources"]["MemoryBytes"],
                    "cpus": node["Description"]["Resources"]["NanoCPUs"] / 1e9,
                },
            }
            for node in nodes_list
        },
    )
