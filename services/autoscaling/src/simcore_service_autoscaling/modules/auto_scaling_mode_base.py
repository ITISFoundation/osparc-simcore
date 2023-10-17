from abc import ABC, abstractmethod
from dataclasses import dataclass

from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node as DockerNode
from servicelib.logging_utils import LogLevelInt

from ..models import AssociatedInstance, EC2InstanceData, EC2InstanceType, Resources


@dataclass
class BaseAutoscaling(ABC):  # pragma: no cover
    @staticmethod
    @abstractmethod
    async def get_monitored_nodes(app: FastAPI) -> list[DockerNode]:
        ...

    @staticmethod
    @abstractmethod
    def get_ec2_tags(app: FastAPI) -> dict[str, str]:
        ...

    @staticmethod
    @abstractmethod
    def get_new_node_docker_tags(app: FastAPI) -> dict[DockerLabelKey, str]:
        ...

    @staticmethod
    @abstractmethod
    async def list_unrunnable_tasks(app: FastAPI) -> list:
        ...

    @staticmethod
    @abstractmethod
    def try_assigning_task_to_node(
        task, instance_to_tasks: list[tuple[AssociatedInstance, list]]
    ) -> bool:
        ...

    @staticmethod
    @abstractmethod
    async def try_assigning_task_to_pending_instances(
        app: FastAPI,
        pending_task,
        list_of_pending_instance_to_tasks: list[tuple[EC2InstanceData, list]],
        type_to_instance_map: dict[str, EC2InstanceType],
        *,
        notify_progress: bool
    ) -> bool:
        ...

    @staticmethod
    @abstractmethod
    def try_assigning_task_to_instance_types(
        pending_task,
        list_of_instance_to_tasks: list[tuple[EC2InstanceType, list]],
    ) -> bool:
        ...

    @staticmethod
    @abstractmethod
    async def log_message_from_tasks(
        app: FastAPI, tasks: list, message: str, *, level: LogLevelInt
    ) -> None:
        ...

    @staticmethod
    @abstractmethod
    async def progress_message_from_tasks(
        app: FastAPI, tasks: list, progress: float
    ) -> None:
        ...

    @staticmethod
    @abstractmethod
    def get_max_resources_from_task(task) -> Resources:
        ...

    @staticmethod
    @abstractmethod
    async def compute_node_used_resources(
        app: FastAPI, instance: AssociatedInstance
    ) -> Resources:
        ...

    @staticmethod
    @abstractmethod
    async def compute_cluster_used_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        ...

    @staticmethod
    @abstractmethod
    async def compute_cluster_total_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        ...
