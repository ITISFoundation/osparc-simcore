import collections
import logging
from typing import cast

from aws_library.ec2 import EC2InstanceData, EC2Tags, Resources
from fastapi import FastAPI
from models_library.clusters import InternalClusterAuthentication
from models_library.docker import (
    DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY,
    DockerLabelKey,
)
from models_library.generated_models.docker_rest_api import Node
from pydantic import AnyUrl, ByteSize
from servicelib.logging_utils import LogLevelInt
from servicelib.utils import logged_gather
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.errors import (
    DaskNoWorkersError,
    DaskSchedulerNotFoundError,
    DaskWorkerNotFoundError,
)
from ..core.settings import get_application_settings
from ..models import AssociatedInstance, DaskTask
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


def _scheduler_auth(app: FastAPI) -> InternalClusterAuthentication:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_DASK  # nosec
    return app_settings.AUTOSCALING_DASK.DASK_SCHEDULER_AUTH


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
        try:
            unrunnable_tasks = await dask.list_unrunnable_tasks(
                _scheduler_url(app), _scheduler_auth(app)
            )
            # NOTE: any worker "processing" more than 1 task means that the other tasks are queued!
            processing_tasks_by_worker = await dask.list_processing_tasks_per_worker(
                _scheduler_url(app), _scheduler_auth(app)
            )
            queued_tasks = []
            for tasks in processing_tasks_by_worker.values():
                queued_tasks += tasks[1:]
            _logger.debug(
                "found %s unrunnable tasks and %s potentially queued tasks",
                len(unrunnable_tasks),
                len(queued_tasks),
            )
            return unrunnable_tasks + queued_tasks
        except DaskSchedulerNotFoundError:
            _logger.warning(
                "No dask scheduler found. TIP: Normal during machine startup."
            )
            return []

    @staticmethod
    async def log_message_from_tasks(
        app: FastAPI, tasks: list, message: str, *, level: LogLevelInt
    ) -> None:
        assert app  # nosec
        assert tasks is not None  # nosec
        _logger.log(level, "LOG: %s", message)

    @staticmethod
    async def progress_message_from_tasks(app: FastAPI, tasks: list, progress: float):
        assert app  # nosec
        assert tasks is not None  # nosec
        _logger.info("PROGRESS: %s", f"{progress:.2f}")

    @staticmethod
    def get_task_required_resources(task) -> Resources:
        return utils.resources_from_dask_task(task)

    @staticmethod
    async def get_task_defined_instance(app: FastAPI, task) -> InstanceTypeType | None:
        assert app  # nosec
        return cast(InstanceTypeType | None, utils.get_task_instance_restriction(task))

    @staticmethod
    async def compute_node_used_resources(
        app: FastAPI, instance: AssociatedInstance
    ) -> Resources:
        try:
            resource = await dask.get_worker_used_resources(
                _scheduler_url(app), _scheduler_auth(app), instance.ec2_instance
            )
            if resource == Resources.create_as_empty():
                num_results_in_memory = (
                    await dask.get_worker_still_has_results_in_memory(
                        _scheduler_url(app), _scheduler_auth(app), instance.ec2_instance
                    )
                )
                if num_results_in_memory > 0:
                    _logger.debug(
                        "found %s for %s",
                        f"{num_results_in_memory=}",
                        f"{instance.ec2_instance.id}",
                    )
                    # NOTE: this is a trick to consider the node still useful
                    return Resources(cpus=0, ram=ByteSize(1024 * 1024 * 1024))

            _logger.debug(
                "found %s for %s", f"{resource=}", f"{instance.ec2_instance.id}"
            )
            return resource
        except (DaskWorkerNotFoundError, DaskNoWorkersError):
            _logger.debug("no resource found for %s", f"{instance.ec2_instance.id}")
            return Resources.create_as_empty()

    @staticmethod
    async def compute_cluster_used_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        list_of_used_resources: list[Resources] = await logged_gather(
            *(
                ComputationalAutoscaling.compute_node_used_resources(app, i)
                for i in instances
            )
        )
        counter = collections.Counter({k: 0 for k in Resources.model_fields})
        for result in list_of_used_resources:
            counter.update(result.model_dump())
        return Resources.model_validate(dict(counter))

    @staticmethod
    async def compute_cluster_total_resources(
        app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        try:
            return await dask.compute_cluster_total_resources(
                _scheduler_url(app), _scheduler_auth(app), instances
            )
        except DaskNoWorkersError:
            return Resources.create_as_empty()

    @staticmethod
    async def is_instance_active(app: FastAPI, instance: AssociatedInstance) -> bool:
        if not utils_docker.is_node_osparc_ready(instance.node):
            return False

        # now check if dask-scheduler/dask-worker is available and running
        return await dask.is_worker_connected(
            _scheduler_url(app), _scheduler_auth(app), instance.ec2_instance
        )

    @staticmethod
    async def is_instance_retired(app: FastAPI, instance: AssociatedInstance) -> bool:
        if not utils_docker.is_node_osparc_ready(instance.node):
            return False
        return await dask.is_worker_retired(
            _scheduler_url(app), _scheduler_auth(app), instance.ec2_instance
        )

    @staticmethod
    async def try_retire_nodes(app: FastAPI) -> None:
        await dask.try_retire_nodes(_scheduler_url(app), _scheduler_auth(app))
