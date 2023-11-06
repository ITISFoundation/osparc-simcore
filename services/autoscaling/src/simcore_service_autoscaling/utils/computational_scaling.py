import datetime
import logging
from typing import Final

from dask_task_models_library.constants import DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY
from fastapi import FastAPI
from servicelib.utils_formatting import timedelta_as_minute_second
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.settings import get_application_settings
from ..models import (
    AssociatedInstance,
    DaskTask,
    EC2InstanceData,
    EC2InstanceType,
    Resources,
)
from . import utils_docker

_logger = logging.getLogger(__name__)

_DEFAULT_MAX_CPU: Final[float] = 1
_DEFAULT_MAX_RAM: Final[int] = 1024


def get_max_resources_from_dask_task(task: DaskTask) -> Resources:
    return Resources(
        cpus=task.required_resources.get("CPU", _DEFAULT_MAX_CPU),
        ram=task.required_resources.get("RAM", _DEFAULT_MAX_RAM),
    )


def get_task_instance_restriction(task: DaskTask) -> InstanceTypeType | None:
    return task.required_resources.get(DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY)


def _compute_tasks_needed_resources(tasks: list[DaskTask]) -> Resources:
    total = Resources.create_as_empty()
    for t in tasks:
        total += get_max_resources_from_dask_task(t)
    return total


def try_assigning_task_to_node(
    pending_task: DaskTask,
    instance_to_tasks: list[tuple[AssociatedInstance, list[DaskTask]]],
) -> bool:
    filtered_list_of_instance_to_tasks = instance_to_tasks
    task_instance_restriction = get_task_instance_restriction(pending_task)
    if task_instance_restriction:

        def _by_instance_type(
            instance_to_task: tuple[AssociatedInstance, list[DaskTask]]
        ) -> bool:
            ass_instance, _ = instance_to_task
            return bool(ass_instance.ec2_instance.type == task_instance_restriction)

        filtered_list_of_instance_to_tasks = filter(
            _by_instance_type, instance_to_tasks
        )
    for instance, node_assigned_tasks in filtered_list_of_instance_to_tasks:
        instance_total_resource = utils_docker.get_node_total_resources(instance.node)
        tasks_needed_resources = _compute_tasks_needed_resources(node_assigned_tasks)
        if (
            instance_total_resource - tasks_needed_resources
        ) >= get_max_resources_from_dask_task(pending_task):
            node_assigned_tasks.append(pending_task)
            return True
    return False


async def try_assigning_task_to_pending_instances(
    app: FastAPI,
    pending_task: DaskTask,
    list_of_pending_instance_to_tasks: list[tuple[EC2InstanceData, list[DaskTask]]],
    type_to_instance_map: dict[str, EC2InstanceType],
    *,
    notify_progress: bool,
) -> bool:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    instance_max_time_to_start = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )

    filtered_list_of_instance_to_tasks = iter(list_of_pending_instance_to_tasks)
    task_instance_restriction = get_task_instance_restriction(pending_task)
    if task_instance_restriction:

        def _by_instance_type(
            instance_to_task: tuple[EC2InstanceData, list[DaskTask]]
        ) -> bool:
            instance_data, _ = instance_to_task
            return bool(instance_data.type == task_instance_restriction)

        filtered_list_of_instance_to_tasks = filter(
            _by_instance_type, list_of_pending_instance_to_tasks
        )

    for instance, instance_assigned_tasks in filtered_list_of_instance_to_tasks:
        instance_type = type_to_instance_map[instance.type]
        instance_total_resources = Resources(
            cpus=instance_type.cpus, ram=instance_type.ram
        )
        tasks_needed_resources = _compute_tasks_needed_resources(
            instance_assigned_tasks
        )
        if (
            instance_total_resources - tasks_needed_resources
        ) >= get_max_resources_from_dask_task(pending_task):
            instance_assigned_tasks.append(pending_task)
            if notify_progress:
                now = datetime.datetime.now(datetime.timezone.utc)
                time_since_launch = now - instance.launch_time
                estimated_time_to_completion = (
                    instance.launch_time + instance_max_time_to_start - now
                )
                _logger.info(
                    "LOG: %s",
                    f"adding machines to the cluster (time waiting: {timedelta_as_minute_second(time_since_launch)},"
                    f" est. remaining time: {timedelta_as_minute_second(estimated_time_to_completion)})...please wait...",
                )
                _logger.info(
                    "PROGRESS: %s",
                    time_since_launch.total_seconds()
                    / instance_max_time_to_start.total_seconds(),
                )
            return True
    return False


def try_assigning_task_to_instance_types(
    pending_task: DaskTask,
    list_of_instance_to_tasks: list[tuple[EC2InstanceType, list[DaskTask]]],
) -> bool:
    filtered_list_of_instance_to_tasks = iter(list_of_instance_to_tasks)
    task_instance_restriction = get_task_instance_restriction(pending_task)
    if task_instance_restriction:

        def _by_instance_type(
            instance_to_task: tuple[EC2InstanceType, list[DaskTask]]
        ) -> bool:
            instance_type, _ = instance_to_task
            return bool(instance_type.name == task_instance_restriction)

        filtered_list_of_instance_to_tasks = filter(
            _by_instance_type, list_of_instance_to_tasks
        )

    for instance, instance_assigned_tasks in filtered_list_of_instance_to_tasks:
        instance_total_resource = Resources(cpus=instance.cpus, ram=instance.ram)
        tasks_needed_resources = _compute_tasks_needed_resources(
            instance_assigned_tasks
        )
        if (
            instance_total_resource - tasks_needed_resources
        ) >= get_max_resources_from_dask_task(pending_task):
            instance_assigned_tasks.append(pending_task)
            return True
    return False
