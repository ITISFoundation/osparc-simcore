from collections.abc import Iterable

from aws_library.ec2.models import EC2InstanceData, EC2Tags, Resources
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node, Task
from servicelib.logging_utils import LogLevelInt
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.settings import get_application_settings
from ..models import (
    AssignedTasksToInstance,
    AssignedTasksToInstanceType,
    AssociatedInstance,
)
from ..utils import dynamic_scaling as utils
from ..utils import utils_docker, utils_ec2
from ..utils.rabbitmq import log_tasks_message, progress_tasks_message
from .auto_scaling_mode_base import BaseAutoscaling
from .docker import get_docker_client


class DynamicAutoscaling(BaseAutoscaling):
    @staticmethod
    async def get_monitored_nodes(app: FastAPI) -> list[Node]:
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        return await utils_docker.get_monitored_nodes(
            get_docker_client(app),
            node_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
        )

    @staticmethod
    def get_ec2_tags(app: FastAPI) -> EC2Tags:
        app_settings = get_application_settings(app)
        return utils_ec2.get_ec2_tags_dynamic(app_settings)

    @staticmethod
    def get_new_node_docker_tags(
        app: FastAPI, ec2_instance_data: EC2InstanceData
    ) -> dict[DockerLabelKey, str]:
        app_settings = get_application_settings(app)
        return utils_docker.get__new_node_docker_tags(app_settings, ec2_instance_data)

    @staticmethod
    async def list_unrunnable_tasks(app: FastAPI) -> list[Task]:
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        return await utils_docker.pending_service_tasks_with_insufficient_resources(
            get_docker_client(app),
            service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
        )

    @staticmethod
    def try_assigning_task_to_node(
        task, instances_to_tasks: Iterable[tuple[AssociatedInstance, list]]
    ) -> bool:
        return utils.try_assigning_task_to_node(task, instances_to_tasks)

    @staticmethod
    async def try_assigning_task_to_instances(
        app: FastAPI,
        pending_task,
        instances_to_tasks: list[AssignedTasksToInstance],
        *,
        notify_progress: bool
    ) -> bool:
        return await utils.try_assigning_task_to_instances(
            app,
            pending_task,
            instances_to_tasks,
            notify_progress=notify_progress,
        )

    @staticmethod
    def try_assigning_task_to_instance_types(
        pending_task,
        instance_types_to_tasks: list[AssignedTasksToInstanceType],
    ) -> bool:
        return utils.try_assigning_task_to_instance_types(
            pending_task, instance_types_to_tasks
        )

    @staticmethod
    async def log_message_from_tasks(
        app: FastAPI, tasks: list, message: str, *, level: LogLevelInt
    ) -> None:
        await log_tasks_message(app, tasks, message, level=level)

    @staticmethod
    async def progress_message_from_tasks(
        app: FastAPI, tasks: list, progress: float
    ) -> None:
        await progress_tasks_message(app, tasks, progress=progress)

    @staticmethod
    def get_max_resources_from_task(task) -> Resources:
        return utils_docker.get_max_resources_from_docker_task(task)

    @staticmethod
    async def get_task_defined_instance(app: FastAPI, task) -> InstanceTypeType | None:
        return await utils_docker.get_task_instance_restriction(
            get_docker_client(app), task
        )

    @staticmethod
    async def compute_node_used_resources(
        app: FastAPI, instance: AssociatedInstance
    ) -> Resources:
        docker_client = get_docker_client(app)
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        return await utils_docker.compute_node_used_resources(
            docker_client,
            instance.node,
            service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
        )

    @staticmethod
    async def compute_cluster_used_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        docker_client = get_docker_client(app)
        return await utils_docker.compute_cluster_used_resources(
            docker_client, [i.node for i in instances]
        )

    @staticmethod
    async def compute_cluster_total_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        assert app  # nosec
        return await utils_docker.compute_cluster_total_resources(
            [i.node for i in instances]
        )
