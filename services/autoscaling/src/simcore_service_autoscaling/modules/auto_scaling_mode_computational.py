import collections
import logging
from collections.abc import Iterable

from aws_library.ec2.models import EC2InstanceData, EC2Tags, Resources
from fastapi import FastAPI
from models_library.docker import (
    DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY,
    DockerLabelKey,
)
from models_library.generated_models.docker_rest_api import Node
from pydantic import AnyUrl, ByteSize
from servicelib.logging_utils import LogLevelInt
from servicelib.utils import logged_gather
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.settings import get_application_settings
from ..models import (
    AssignedTasksToInstance,
    AssignedTasksToInstanceType,
    AssociatedInstance,
    DaskTask,
)
from ..utils import computational_scaling as utils
from ..utils import utils_docker, utils_ec2
from . import dask
from .auto_scaling_mode_base import BaseAutoscaling
from .docker import get_docker_client

_logger = logging.getLogger(__name__)


def _scheduler_url(app: FastAPI) -> AnyUrl:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_DASK  # nosec
    return app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL


class ComputationalAutoscaling(BaseAutoscaling):
    @staticmethod
    async def get_monitored_nodes(app: FastAPI) -> list[Node]:
        return await utils_docker.get_worker_nodes(get_docker_client(app))

    @staticmethod
    def get_ec2_tags(app: FastAPI) -> EC2Tags:
        app_settings = get_application_settings(app)
        return utils_ec2.get_ec2_tags_computational(app_settings)

    @staticmethod
    def get_new_node_docker_tags(
        app: FastAPI, ec2_instance_data: EC2InstanceData
    ) -> dict[DockerLabelKey, str]:
        assert app  # nosec
        return {
            DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY: ec2_instance_data.type
        }

    @staticmethod
    async def list_unrunnable_tasks(app: FastAPI) -> list[DaskTask]:
        return await dask.list_unrunnable_tasks(_scheduler_url(app))

    @staticmethod
    def try_assigning_task_to_node(
        task: DaskTask,
        instances_to_tasks: Iterable[tuple[AssociatedInstance, list[DaskTask]]],
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
        assert app  # nosec
        assert tasks  # nosec
        _logger.log(level, "LOG: %s", message)

    @staticmethod
    async def progress_message_from_tasks(app: FastAPI, tasks: list, progress: float):
        assert app  # nosec
        assert tasks  # nosec
        _logger.info("PROGRESS: %s", progress)

    @staticmethod
    def get_max_resources_from_task(task) -> Resources:
        return utils.get_max_resources_from_dask_task(task)

    @staticmethod
    async def get_task_defined_instance(app: FastAPI, task) -> InstanceTypeType | None:
        assert app  # nosec
        return utils.get_task_instance_restriction(task)

    @staticmethod
    async def compute_node_used_resources(
        app: FastAPI, instance: AssociatedInstance
    ) -> Resources:
        num_results_in_memory = await dask.get_worker_still_has_results_in_memory(
            _scheduler_url(app), instance.ec2_instance
        )
        if num_results_in_memory > 0:
            # NOTE: this is a trick to consider the node still useful
            return Resources(cpus=1, ram=ByteSize())
        return await dask.get_worker_used_resources(
            _scheduler_url(app), instance.ec2_instance
        )

    @staticmethod
    async def compute_cluster_used_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        list_of_used_resources = await logged_gather(
            *(
                ComputationalAutoscaling.compute_node_used_resources(app, i)
                for i in instances
            )
        )
        counter = collections.Counter({k: 0 for k in Resources.__fields__})
        for result in list_of_used_resources:
            counter.update(result.dict())
        return Resources.parse_obj(dict(counter))

    @staticmethod
    async def compute_cluster_total_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        return await dask.compute_cluster_total_resources(
            _scheduler_url(app), instances
        )
