import collections
import logging
from typing import Any, cast

from aws_library.ec2 import EC2InstanceData, EC2Tags, Resources
from fastapi import FastAPI
from models_library.clusters import ClusterAuthentication
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node
from models_library.services_metadata_runtime import (
    DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY,
)
from pydantic import AnyUrl, ByteSize
from servicelib.utils import logged_gather
from types_aiobotocore_ec2.literals import InstanceTypeType

from ...core.errors import (
    DaskNoWorkersError,
    DaskSchedulerNotFoundError,
    DaskWorkerNotFoundError,
)
from ...core.settings import get_application_settings
from ...models import AssociatedInstance, DaskTask
from ...utils import utils_docker, utils_ec2
from .. import dask
from ..docker import get_docker_client
from . import _utils_computational as utils

_logger = logging.getLogger(__name__)


def _scheduler_url(app: FastAPI) -> AnyUrl:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_DASK  # nosec
    return app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL


def _scheduler_auth(app: FastAPI) -> ClusterAuthentication:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_DASK  # nosec
    return app_settings.AUTOSCALING_DASK.DASK_SCHEDULER_AUTH


class ComputationalAutoscalingProvider:
    async def get_monitored_nodes(self, app: FastAPI) -> list[Node]:
        assert self  # nosec
        return await utils_docker.get_worker_nodes(get_docker_client(app))

    def get_ec2_tags(self, app: FastAPI) -> EC2Tags:
        assert self  # nosec
        app_settings = get_application_settings(app)
        return utils_ec2.get_ec2_tags_computational(app_settings)

    def get_new_node_docker_tags(
        self, app: FastAPI, ec2_instance_data: EC2InstanceData
    ) -> dict[DockerLabelKey, str]:
        assert self  # nosec
        assert app  # nosec
        return {
            DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY: ec2_instance_data.type
        }

    async def list_unrunnable_tasks(self, app: FastAPI) -> list[DaskTask]:
        assert self  # nosec
        try:
            unrunnable_tasks = await dask.list_unrunnable_tasks(
                _scheduler_url(app), _scheduler_auth(app)
            )
            # NOTE: any worker "processing" more than 1 task means that the other tasks are queued!
            # NOTE: that is not necessarily true, in cases where 1 worker takes multiple tasks?? (osparc.io)
            processing_tasks_by_worker = await dask.list_processing_tasks_per_worker(
                _scheduler_url(app), _scheduler_auth(app)
            )
            queued_tasks = []
            for tasks in processing_tasks_by_worker.values():
                queued_tasks += tasks[1:]
            _logger.debug(
                "found %s pending tasks and %s potentially queued tasks",
                len(unrunnable_tasks),
                len(queued_tasks),
            )
            return unrunnable_tasks + queued_tasks
        except DaskSchedulerNotFoundError:
            _logger.warning(
                "No dask scheduler found. TIP: Normal during machine startup."
            )
            return []

    def get_task_required_resources(self, task) -> Resources:
        assert self  # nosec
        return utils.resources_from_dask_task(task)

    async def get_task_defined_instance(
        self, app: FastAPI, task
    ) -> InstanceTypeType | None:
        assert self  # nosec
        assert app  # nosec
        return cast(InstanceTypeType | None, utils.get_task_instance_restriction(task))

    async def compute_node_used_resources(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> Resources:
        assert self  # nosec
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

    async def compute_cluster_used_resources(
        self, app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        assert self  # nosec
        list_of_used_resources: list[Resources] = await logged_gather(
            *(self.compute_node_used_resources(app, i) for i in instances)
        )
        counter: collections.Counter = collections.Counter()
        for result in list_of_used_resources:
            counter.update(result.as_flat_dict())

        flat_counter: dict[str, Any] = dict(counter)
        flat_counter.setdefault("cpus", 0)
        flat_counter.setdefault("ram", 0)
        return Resources.from_flat_dict(flat_counter)

    async def compute_cluster_total_resources(
        self, app: FastAPI, instances: list[AssociatedInstance]
    ) -> Resources:
        assert self  # nosec
        try:
            return await dask.compute_cluster_total_resources(
                _scheduler_url(app),
                _scheduler_auth(app),
                [i.ec2_instance for i in instances],
            )
        except DaskNoWorkersError:
            return Resources.create_as_empty()

    async def is_instance_active(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> bool:
        assert self  # nosec
        if not utils_docker.is_node_osparc_ready(instance.node):
            return False

        # now check if dask-scheduler/dask-worker is available and running
        return await dask.is_worker_connected(
            _scheduler_url(app), _scheduler_auth(app), instance.ec2_instance
        )

    async def is_instance_retired(
        self, app: FastAPI, instance: AssociatedInstance
    ) -> bool:
        assert self  # nosec
        if not utils_docker.is_node_osparc_ready(instance.node):
            return False
        return await dask.is_worker_retired(
            _scheduler_url(app), _scheduler_auth(app), instance.ec2_instance
        )

    async def try_retire_nodes(self, app: FastAPI) -> None:
        assert self  # nosec
        await dask.try_retire_nodes(_scheduler_url(app), _scheduler_auth(app))
