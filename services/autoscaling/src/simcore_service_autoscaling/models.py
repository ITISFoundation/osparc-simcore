import datetime
from dataclasses import dataclass, field

from models_library.generated_models.docker_rest_api import Node, Task
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.users import UserID
from pydantic import BaseModel, ByteSize, Field, NonNegativeFloat, PositiveInt
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType


class SimcoreServiceDockerLabelKeys(BaseModel):
    # NOTE: in a next PR, this should be moved to packages models-library and used
    # all over, and aliases should use io.simcore.service.*
    # https://github.com/ITISFoundation/osparc-simcore/issues/3638

    user_id: UserID = Field(..., alias="user_id")
    project_id: ProjectID = Field(..., alias="study_id")
    node_id: NodeID = Field(..., alias="uuid")

    def to_docker_labels(self) -> dict[str, str]:
        """returns a dictionary of strings as required by docker"""
        std_export = self.dict(by_alias=True)
        return {k: f"{v}" for k, v in std_export.items()}

    @classmethod
    def from_docker_task(cls, docker_task: Task) -> "SimcoreServiceDockerLabelKeys":
        assert docker_task.Spec  # nosec
        assert docker_task.Spec.ContainerSpec  # nosec
        task_labels = docker_task.Spec.ContainerSpec.Labels or {}
        return cls.parse_obj(task_labels)

    class Config:
        allow_population_by_field_name = True


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
                for (key, a), b in zip(self.dict().items(), other.dict().values())
            }
        )

    def __sub__(self, other: "Resources") -> "Resources":
        return Resources.construct(
            **{
                key: a - b
                for (key, a), b in zip(self.dict().items(), other.dict().values())
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
