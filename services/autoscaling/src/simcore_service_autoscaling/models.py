from dataclasses import dataclass, field
from typing import Any, TypeAlias

from aws_library.ec2.models import EC2InstanceData
from models_library.generated_models.docker_rest_api import Node


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


DaskTaskId: TypeAlias = str
DaskTaskResources: TypeAlias = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class DaskTask:
    task_id: DaskTaskId
    required_resources: DaskTaskResources
