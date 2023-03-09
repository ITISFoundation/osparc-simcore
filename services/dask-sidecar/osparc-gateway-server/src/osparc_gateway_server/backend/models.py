from ipaddress import IPv4Address
from typing import (
    Any,
    Generic,
    ItemsView,
    Iterator,
    KeysView,
    Optional,
    TypeVar,
    Union,
    ValuesView,
)

from pydantic import BaseModel, ByteSize, Field, PositiveFloat
from pydantic.generics import GenericModel

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


DictKey = TypeVar("DictKey")
DictValue = TypeVar("DictValue")


class DictModel(GenericModel, Generic[DictKey, DictValue]):
    __root__: dict[DictKey, DictValue]

    def __getitem__(self, k: DictKey) -> DictValue:
        return self.__root__.__getitem__(k)

    def __setitem__(self, k: DictKey, v: DictValue) -> None:
        self.__root__.__setitem__(k, v)

    def items(self) -> ItemsView[DictKey, DictValue]:
        return self.__root__.items()

    def keys(self) -> KeysView[DictKey]:
        return self.__root__.keys()

    def values(self) -> ValuesView[DictValue]:
        return self.__root__.values()

    def pop(self, key: DictKey) -> DictValue:
        return self.__root__.pop(key)

    def __iter__(self) -> Iterator[DictKey]:
        return self.__root__.__iter__()

    def get(
        self, key: DictKey, default: Optional[DictValue] = None
    ) -> Optional[DictValue]:
        return self.__root__.get(key, default)

    def __len__(self) -> int:
        return self.__root__.__len__()


class ClusterInformation(DictModel[Hostname, NodeInformation]):
    @staticmethod
    def from_docker(nodes_list: list[dict[str, Any]]) -> "ClusterInformation":
        return ClusterInformation.parse_obj(
            {
                node["Description"]["Hostname"]: {
                    "docker_node_id": node["ID"],
                    "ip": node["Status"]["Addr"],
                    "resources": {
                        "memory": node["Description"]["Resources"]["MemoryBytes"],
                        "cpus": node["Description"]["Resources"]["NanoCPUs"] / 1e9,
                        # "others": node["Description"]["Resources"]["GenericResources"],
                    },
                }
                for node in nodes_list
            }
        )
