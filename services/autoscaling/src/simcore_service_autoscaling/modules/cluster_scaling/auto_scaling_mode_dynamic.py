from aws_library.ec2 import EC2InstanceData, EC2Tags, Resources
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node, Task
from types_aiobotocore_ec2.literals import InstanceTypeType

from ...core.settings import get_application_settings
from ...models import AssociatedInstance
from ...utils import utils_docker, utils_ec2
from ..docker import get_docker_client


class DynamicAutoscaling:
    async def get_monitored_nodes(self, app: FastAPI) -> list[Node]:
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        return await utils_docker.get_monitored_nodes(
            get_docker_client(app),
            node_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
        )

    def get_ec2_tags(self, app: FastAPI) -> EC2Tags:
        app_settings = get_application_settings(app)
        return utils_ec2.get_ec2_tags_dynamic(app_settings)

    def get_new_node_docker_tags(
        self, app: FastAPI, ec2_instance_data: EC2InstanceData
    ) -> dict[DockerLabelKey, str]:
        app_settings = get_application_settings(app)
        return utils_docker.get_new_node_docker_tags(app_settings, ec2_instance_data)

    async def list_unrunnable_tasks(self, app: FastAPI) -> list[Task]:
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        return await utils_docker.pending_service_tasks_with_insufficient_resources(
            get_docker_client(app),
            service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
        )

    def get_task_required_resources(self, task) -> Resources:
        return utils_docker.get_max_resources_from_docker_task(task)

    async def get_task_defined_instance(
        self, app: FastAPI, task
    ) -> InstanceTypeType | None:
        return await utils_docker.get_task_instance_restriction(
            get_docker_client(app), task
        )

    async def compute_node_used_resources(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> Resources:
        docker_client = get_docker_client(app)
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        return await utils_docker.compute_node_used_resources(
            docker_client,
            instance.node,
            service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
        )

    async def compute_cluster_used_resources(
        self, app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        docker_client = get_docker_client(app)
        return await utils_docker.compute_cluster_used_resources(
            docker_client, [i.node for i in instances]
        )

    async def compute_cluster_total_resources(
        self, app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        assert app  # nosec
        return await utils_docker.compute_cluster_total_resources(
            [i.node for i in instances]
        )

    async def is_instance_active(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> bool:
        assert app  # nosec
        return utils_docker.is_node_osparc_ready(instance.node)

    async def is_instance_retired(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> bool:
        assert app  # nosec
        assert instance  # nosec
        # nothing to do here
        return False

    async def try_retire_nodes(self, app: FastAPI) -> None:
        assert app  # nosec
        # nothing to do here
