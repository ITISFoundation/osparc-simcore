import dataclasses
from typing import Final

from aws_library.ec2 import EC2InstanceData, EC2Tags, Resources
from aws_library.ec2._models import EC2InstanceType
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node, Task
from pydantic import ByteSize, TypeAdapter
from types_aiobotocore_ec2.literals import InstanceTypeType

from ...core.settings import get_application_settings
from ...models import AssociatedInstance
from ...utils import utils_docker, utils_ec2
from ..docker import get_docker_client

_MACHINE_TOTAL_RAM_SAFE_MARGIN_RATIO: Final[float] = (
    0.1  # NOTE: machines always have less available RAM than advertised
)
_SIDECARS_OPS_SAFE_RAM_MARGIN: Final[ByteSize] = TypeAdapter(ByteSize).validate_python(
    "1GiB"
)
_CPUS_SAFE_MARGIN: Final[float] = 1.4
_MIN_NUM_CPUS: Final[float] = 0.5


class DynamicAutoscalingProvider:
    async def get_monitored_nodes(self, app: FastAPI) -> list[Node]:
        assert self  # nosec
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        return await utils_docker.get_monitored_nodes(
            get_docker_client(app),
            node_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
        )

    def get_ec2_tags(self, app: FastAPI) -> EC2Tags:
        assert self  # nosec
        app_settings = get_application_settings(app)
        return utils_ec2.get_ec2_tags_dynamic(app_settings)

    def get_new_node_docker_tags(
        self, app: FastAPI, ec2_instance_data: EC2InstanceData
    ) -> dict[DockerLabelKey, str]:
        assert self  # nosec
        app_settings = get_application_settings(app)
        return utils_docker.get_new_node_docker_tags(app_settings, ec2_instance_data)

    async def list_unrunnable_tasks(self, app: FastAPI) -> list[Task]:
        assert self  # nosec
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
        return await utils_docker.pending_service_tasks_with_insufficient_resources(
            get_docker_client(app),
            service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
        )

    def get_task_required_resources(self, task) -> Resources:
        assert self  # nosec
        return utils_docker.get_max_resources_from_docker_task(task)

    async def get_task_defined_instance(
        self, app: FastAPI, task
    ) -> InstanceTypeType | None:
        assert self  # nosec
        return await utils_docker.get_task_instance_restriction(
            get_docker_client(app), task
        )

    async def compute_node_used_resources(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> Resources:
        assert self  # nosec
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
        assert self  # nosec
        docker_client = get_docker_client(app)
        return await utils_docker.compute_cluster_used_resources(
            docker_client, [i.node for i in instances]
        )

    async def compute_cluster_total_resources(
        self, app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        assert self  # nosec
        assert app  # nosec
        return await utils_docker.compute_cluster_total_resources(
            [i.node for i in instances]
        )

    async def is_instance_active(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> bool:
        assert self  # nosec
        assert app  # nosec
        return utils_docker.is_node_osparc_ready(instance.node)

    async def is_instance_retired(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> bool:
        assert self  # nosec
        assert app  # nosec
        assert instance  # nosec
        # nothing to do here
        return False

    async def try_retire_nodes(self, app: FastAPI) -> None:
        assert self  # nosec
        assert app  # nosec
        # nothing to do here

    def add_instance_generic_resources(
        self, app: FastAPI, instance: EC2InstanceData
    ) -> None:
        assert self  # nosec
        assert app  # nosec
        assert instance  # nosec
        # nothing to do at the moment

    def adjust_instance_type_resources(
        self, app: FastAPI, instance_type: EC2InstanceType
    ) -> EC2InstanceType:
        assert self  # nosec
        assert app  # nosec
        # nothing to do at the moment
        adjusted_cpus = float(instance_type.resources.cpus) - _CPUS_SAFE_MARGIN
        adjusted_ram = int(
            instance_type.resources.ram
            - _MACHINE_TOTAL_RAM_SAFE_MARGIN_RATIO * instance_type.resources.ram
            - _SIDECARS_OPS_SAFE_RAM_MARGIN
        )
        return dataclasses.replace(
            instance_type,
            resources=instance_type.resources.model_copy(
                update={"cpus": adjusted_cpus, "ram": ByteSize(adjusted_ram)}
            ),
        )
