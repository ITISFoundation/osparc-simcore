from dataclasses import dataclass, field
from typing import TypeAlias

from aws_library.ec2.models import EC2InstanceData, EC2InstanceType, Resources
from dask_task_models_library.resource_constraints import DaskTaskResources
from models_library.generated_models.docker_rest_api import Node


@dataclass(frozen=True, slots=True, kw_only=True)
class _TaskAssignmentMixin:
    assigned_tasks: list = field(default_factory=list)
    available_resources: Resources = field(default_factory=Resources.create_as_empty)

    def assign_task(self, task, task_resources: Resources) -> None:
        self.assigned_tasks.append(task)
        object.__setattr__(
            self, "available_resources", self.available_resources - task_resources
        )

    def has_resources_for_task(self, task_resources: Resources) -> bool:
        return bool(self.available_resources >= task_resources)


@dataclass(frozen=True, kw_only=True, slots=True)
class AssignedTasksToInstanceType(_TaskAssignmentMixin):
    instance_type: EC2InstanceType


@dataclass(frozen=True, kw_only=True, slots=True)
class _BaseInstance(_TaskAssignmentMixin):
    ec2_instance: EC2InstanceData

    def __post_init__(self) -> None:
        if self.available_resources == Resources.create_as_empty():
            object.__setattr__(self, "available_resources", self.ec2_instance.resources)


@dataclass(frozen=True, kw_only=True, slots=True)
class AssociatedInstance(_BaseInstance):
    node: Node


@dataclass(frozen=True, kw_only=True, slots=True)
class NonAssociatedInstance(_BaseInstance):
    ...


@dataclass(frozen=True, kw_only=True, slots=True)
class Cluster:
    active_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2-backed docker node which is active and ready to receive tasks (or with running tasks)"
        }
    )
    pending_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2-backed docker node which is active and NOT yet ready to receive tasks"
        }
    )
    drained_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2-backed docker node which is drained (cannot accept tasks)"
        }
    )
    reserve_drained_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2-backed docker node which is drained in the reserve if this is enabled (with no tasks)"
        }
    )
    pending_ec2s: list[NonAssociatedInstance] = field(
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

    def can_scale_down(self) -> bool:
        return bool(
            self.active_nodes
            or self.pending_nodes
            or self.drained_nodes
            or self.pending_ec2s
        )

    def total_number_of_machines(self) -> int:
        return (
            len(self.active_nodes)
            + len(self.pending_nodes)
            + len(self.drained_nodes)
            + len(self.reserve_drained_nodes)
            + len(self.pending_ec2s)
        )


DaskTaskId: TypeAlias = str


@dataclass(frozen=True, kw_only=True)
class DaskTask:
    task_id: DaskTaskId
    required_resources: DaskTaskResources
