from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node, Task
from servicelib.logging_utils import LogLevelInt

from ..core.settings import get_application_settings
from ..models import AssociatedInstance, EC2InstanceData, EC2InstanceType, Resources
from ..utils import dynamic_scaling as utils
from ..utils import ec2, utils_docker
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
    def get_ec2_tags(app: FastAPI) -> dict[str, str]:
        app_settings = get_application_settings(app)
        return ec2.get_ec2_tags_dynamic(app_settings)

    @staticmethod
    def get_new_node_docker_tags(app: FastAPI) -> dict[DockerLabelKey, str]:
        app_settings = get_application_settings(app)
        return utils_docker.get_docker_tags(app_settings)

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
        task, instance_to_tasks: list[tuple[AssociatedInstance, list]]
    ) -> bool:
        return utils.try_assigning_task_to_node(task, instance_to_tasks)

    @staticmethod
    async def try_assigning_task_to_pending_instances(
        app: FastAPI,
        pending_task,
        list_of_pending_instance_to_tasks: list[tuple[EC2InstanceData, list]],
        type_to_instance_map: dict[str, EC2InstanceType],
        *,
        notify_progress: bool
    ) -> bool:
        return await utils.try_assigning_task_to_pending_instances(
            app,
            pending_task,
            list_of_pending_instance_to_tasks,
            type_to_instance_map,
            notify_progress=notify_progress,
        )

    @staticmethod
    def try_assigning_task_to_instance_types(
        pending_task,
        list_of_instance_to_tasks: list[tuple[EC2InstanceType, list]],
    ) -> bool:
        return utils.try_assigning_task_to_instances(
            pending_task, list_of_instance_to_tasks
        )

    @staticmethod
    async def log_message_from_tasks(
        app: FastAPI, tasks: list, message: str, *, level: LogLevelInt
    ) -> None:
        await log_tasks_message(app, tasks, message, level=level)

    @staticmethod
    async def progress_message_from_tasks(app: FastAPI, tasks: list, progress: float):
        await progress_tasks_message(app, tasks, progress=1.0)

    @staticmethod
    def get_max_resources_from_task(task) -> Resources:
        return utils_docker.get_max_resources_from_docker_task(task)

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
