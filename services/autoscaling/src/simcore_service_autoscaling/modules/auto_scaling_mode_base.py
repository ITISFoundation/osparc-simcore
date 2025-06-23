from abc import ABC, abstractmethod
from dataclasses import dataclass

from aws_library.ec2 import EC2InstanceData, EC2Tags, Resources
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node as DockerNode
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..models import AssociatedInstance


@dataclass
class BaseAutoscaling(ABC):  # pragma: no cover
    @staticmethod
    @abstractmethod
    async def get_monitored_nodes(app: FastAPI) -> list[DockerNode]: ...

    @staticmethod
    @abstractmethod
    def get_ec2_tags(app: FastAPI) -> EC2Tags: ...

    @staticmethod
    @abstractmethod
    def get_new_node_docker_tags(
        app: FastAPI, ec2_instance_data: EC2InstanceData
    ) -> dict[DockerLabelKey, str]: ...

    @staticmethod
    @abstractmethod
    async def list_unrunnable_tasks(app: FastAPI) -> list: ...

    @staticmethod
    @abstractmethod
    def get_task_required_resources(task) -> Resources: ...

    @staticmethod
    @abstractmethod
    async def get_task_defined_instance(
        app: FastAPI, task
    ) -> InstanceTypeType | None: ...

    @staticmethod
    @abstractmethod
    async def compute_node_used_resources(
        app: FastAPI, instance: AssociatedInstance
    ) -> Resources: ...

    @staticmethod
    @abstractmethod
    async def compute_cluster_used_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources: ...

    @staticmethod
    @abstractmethod
    async def compute_cluster_total_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources: ...

    @staticmethod
    @abstractmethod
    async def is_instance_active(
        app: FastAPI, instance: AssociatedInstance
    ) -> bool: ...

    @staticmethod
    @abstractmethod
    async def is_instance_retired(
        app: FastAPI, instance: AssociatedInstance
    ) -> bool: ...

    @staticmethod
    @abstractmethod
    async def try_retire_nodes(app: FastAPI) -> None: ...
