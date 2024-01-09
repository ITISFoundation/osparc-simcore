from dataclasses import dataclass, field
from typing import TypeAlias

from aws_library.ec2.models import EC2InstanceData, EC2InstanceType, Resources
from dask_task_models_library.resource_constraints import DaskTaskResources
from models_library.generated_models.docker_rest_api import Node


@dataclass(frozen=True, kw_only=True)
class AssignedTasksToInstance:
    instance: EC2InstanceData
    available_resources: Resources
    assigned_tasks: list


@dataclass(frozen=True, kw_only=True)
class AssignedTasksToInstanceType:
    instance_type: EC2InstanceType
    assigned_tasks: list


@dataclass(frozen=True)
class AssociatedInstance:
    node: Node
    ec2_instance: EC2InstanceData


@dataclass(frozen=True, kw_only=True, slots=True)
class Cluster:
    active_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is active and ready to receive tasks (or with running tasks)"
        }
    )
    pending_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is active and NOT yet ready to receive tasks"
        }
    )
    drained_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is drained (cannot accept tasks)"
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


@dataclass(frozen=True, kw_only=True)
class DaskTask:
    task_id: DaskTaskId
    required_resources: DaskTaskResources
