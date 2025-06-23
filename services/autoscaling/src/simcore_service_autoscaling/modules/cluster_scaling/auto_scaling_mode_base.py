from typing import Protocol

from aws_library.ec2 import EC2InstanceData, EC2Tags, Resources
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node as DockerNode
from types_aiobotocore_ec2.literals import InstanceTypeType

from ...models import AssociatedInstance


class BaseAutoscaling(Protocol):
    async def get_monitored_nodes(self, app: FastAPI) -> list[DockerNode]: ...

    def get_ec2_tags(self, app: FastAPI) -> EC2Tags: ...

    def get_new_node_docker_tags(
        self, app: FastAPI, ec2_instance_data: EC2InstanceData
    ) -> dict[DockerLabelKey, str]: ...

    async def list_unrunnable_tasks(self, app: FastAPI) -> list: ...

    def get_task_required_resources(self, task) -> Resources: ...

    async def get_task_defined_instance(
        self, app: FastAPI, task
    ) -> InstanceTypeType | None: ...

    async def compute_node_used_resources(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> Resources: ...

    async def compute_cluster_used_resources(
        self, app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources: ...

    async def compute_cluster_total_resources(
        self, app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources: ...

    async def is_instance_active(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> bool: ...

    async def is_instance_retired(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> bool: ...

    async def try_retire_nodes(self, app: FastAPI) -> None: ...
