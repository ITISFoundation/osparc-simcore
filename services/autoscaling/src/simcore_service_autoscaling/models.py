from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from aws_library.ec2 import EC2InstanceData, EC2InstanceType, Resources
from dask_task_models_library.resource_constraints import DaskTaskResources
from models_library.generated_models.docker_rest_api import Node
from types_aiobotocore_ec2.literals import InstanceTypeType


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

    def has_assigned_tasks(self) -> bool:
        return bool(self.available_resources < self.ec2_instance.resources)


@dataclass(frozen=True, kw_only=True, slots=True)
class AssociatedInstance(_BaseInstance):
    node: Node


@dataclass(frozen=True, kw_only=True, slots=True)
class NonAssociatedInstance(_BaseInstance):
    ...


@dataclass(frozen=True, kw_only=True, slots=True)
class Cluster:  # pylint: disable=too-many-instance-attributes
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
    broken_ec2s: list[NonAssociatedInstance] = field(
        metadata={
            "description": "This is an existing EC2 instance that never properly joined the cluster and is deemed as broken and will be terminated"
        }
    )
    buffer_ec2s: list[NonAssociatedInstance] = field(
        metadata={
            "description": "This is a prepared stopped EC2 instance, not yet associated to a docker node, ready to be used"
        }
    )
    disconnected_nodes: list[Node] = field(
        metadata={
            "description": "This is a docker node which is not backed by a running EC2 instance"
        }
    )
    terminating_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2-backed docker node which is docker drained and waiting for termination"
        }
    )
    terminated_instances: list[NonAssociatedInstance]

    def can_scale_down(self) -> bool:
        return bool(
            self.active_nodes
            or self.pending_nodes
            or self.drained_nodes
            or self.pending_ec2s
            or self.terminating_nodes
        )

    def total_number_of_machines(self) -> int:
        """return the number of machines that are swtiched on"""
        return (
            len(self.active_nodes)
            + len(self.pending_nodes)
            + len(self.drained_nodes)
            + len(self.reserve_drained_nodes)
            + len(self.pending_ec2s)
            + len(self.broken_ec2s)
            + len(self.terminating_nodes)
        )

    def __repr__(self) -> str:
        def _get_instance_ids(
            instances: list[AssociatedInstance] | list[NonAssociatedInstance],
        ) -> str:
            return f"[{','.join(n.ec2_instance.id for n in instances)}]"

        return (
            f"active-nodes: count={len(self.active_nodes)} {_get_instance_ids(self.active_nodes)}, "
            f"pending-nodes: count={len(self.pending_nodes)} {_get_instance_ids(self.pending_nodes)}, "
            f"drained-nodes: count={len(self.drained_nodes)} {_get_instance_ids(self.drained_nodes)}, "
            f"reserve-drained-nodes: count={len(self.reserve_drained_nodes)} {_get_instance_ids(self.reserve_drained_nodes)}, "
            f"pending-ec2s: count={len(self.pending_ec2s)} {_get_instance_ids(self.pending_ec2s)}, "
            f"broken-ec2s: count={len(self.broken_ec2s)} {_get_instance_ids(self.broken_ec2s)}, "
            f"buffer-ec2s: count={len(self.buffer_ec2s)} {_get_instance_ids(self.buffer_ec2s)}, "
            f"disconnected-nodes: count={len(self.disconnected_nodes)}, "
            f"terminating-nodes: count={len(self.terminating_nodes)} {_get_instance_ids(self.terminating_nodes)}, "
            f"terminated-ec2s: count={len(self.terminated_instances)} {_get_instance_ids(self.terminated_instances)}, "
        )


DaskTaskId: TypeAlias = str


@dataclass(frozen=True, kw_only=True)
class DaskTask:
    task_id: DaskTaskId
    required_resources: DaskTaskResources


@dataclass(kw_only=True, slots=True)
class BufferPool:
    ready_instances: set[EC2InstanceData] = field(default_factory=set)
    pending_instances: set[EC2InstanceData] = field(default_factory=set)
    waiting_to_pull_instances: set[EC2InstanceData] = field(default_factory=set)
    waiting_to_stop_instances: set[EC2InstanceData] = field(default_factory=set)
    pulling_instances: set[EC2InstanceData] = field(default_factory=set)
    stopping_instances: set[EC2InstanceData] = field(default_factory=set)
    broken_instances: set[EC2InstanceData] = field(default_factory=set)

    def __repr__(self) -> str:
        return (
            f"BufferPool(ready-count={len(self.ready_instances)}, "
            f"pending-count={len(self.pending_instances)}, "
            f"waiting-to-pull-count={len(self.waiting_to_pull_instances)}, "
            f"waiting-to-stop-count={len(self.waiting_to_stop_instances)}, "
            f"pulling-count={len(self.pulling_instances)}, "
            f"stopping-count={len(self.stopping_instances)})"
            f"broken-count={len(self.broken_instances)})"
        )

    def _sort_by_readyness(
        self, *, invert: bool = False
    ) -> Generator[set[EC2InstanceData], Any, None]:
        order = (
            self.ready_instances,
            self.stopping_instances,
            self.waiting_to_stop_instances,
            self.pulling_instances,
            self.waiting_to_pull_instances,
            self.pending_instances,
            self.broken_instances,
        )
        if invert:
            yield from reversed(order)
        else:
            yield from order

    def pre_pulled_instances(self) -> set[EC2InstanceData]:
        """returns all the instances that completed image pre pulling"""
        return self.ready_instances.union(self.stopping_instances)

    def all_instances(self) -> set[EC2InstanceData]:
        """sorted by importance: READY (stopped) > STOPPING >"""
        gen = self._sort_by_readyness()
        return next(gen).union(*(_ for _ in gen))

    def remove_instance(self, instance: EC2InstanceData) -> None:
        for instances in self._sort_by_readyness(invert=True):
            if instance in instances:
                instances.remove(instance)
                break


@dataclass
class BufferPoolManager:
    buffer_pools: dict[InstanceTypeType, BufferPool] = field(
        default_factory=lambda: defaultdict(BufferPool)
    )

    def __repr__(self) -> str:
        return f"BufferPoolManager({dict(self.buffer_pools)})"
