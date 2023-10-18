import datetime
from dataclasses import dataclass, field

from models_library.generated_models.docker_rest_api import Node
from pydantic import BaseModel, ByteSize, NonNegativeFloat, PositiveInt
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType


class Resources(BaseModel):
    cpus: NonNegativeFloat
    ram: ByteSize

    @classmethod
    def create_as_empty(cls) -> "Resources":
        return cls(cpus=0, ram=ByteSize(0))

    def __ge__(self, other: "Resources") -> bool:
        return self.cpus >= other.cpus and self.ram >= other.ram

    def __add__(self, other: "Resources") -> "Resources":
        return Resources.construct(
            **{
                key: a + b
                for (key, a), b in zip(
                    self.dict().items(), other.dict().values(), strict=True
                )
            }
        )

    def __sub__(self, other: "Resources") -> "Resources":
        return Resources.construct(
            **{
                key: a - b
                for (key, a), b in zip(
                    self.dict().items(), other.dict().values(), strict=True
                )
            }
        )


@dataclass(frozen=True)
class EC2InstanceType:
    name: str
    cpus: PositiveInt
    ram: ByteSize


InstancePrivateDNSName = str


@dataclass(frozen=True)
class EC2InstanceData:
    launch_time: datetime.datetime
    id: str
    aws_private_dns: InstancePrivateDNSName
    type: InstanceTypeType
    state: InstanceStateNameType


@dataclass(frozen=True)
class AssociatedInstance:
    node: Node
    ec2_instance: EC2InstanceData


@dataclass(frozen=True)
class Cluster:
    active_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is active (with running tasks)"
        }
    )
    drained_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is drained (with no tasks)"
        }
    )
    reserve_drained_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is drained in the reserve if this is enabled (with no tasks)"
        }
    )
    pending_ec2s: list[EC2InstanceData] = field(
        metadata={
            "description": "This is an EC2 instance that is not yet associated to a docker node"
        }
    )
    disconnected_nodes: list[Node] = field(
        metadata={
            "description": "This is a docker node which is not backed by a running EC2 instance"
        }
    )
    terminated_instances: list[EC2InstanceData]
