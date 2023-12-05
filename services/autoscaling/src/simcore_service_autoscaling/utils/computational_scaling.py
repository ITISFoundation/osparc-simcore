import datetime
import logging
from collections.abc import Iterable
from typing import Final

from aws_library.ec2.models import Resources
from dask_task_models_library.resource_constraints import (
    get_ec2_instance_type_from_resources,
)
from fastapi import FastAPI
from servicelib.utils_formatting import timedelta_as_minute_second

from ..core.settings import get_application_settings
from ..models import (
    AssignedTasksToInstance,
    AssignedTasksToInstanceType,
    AssociatedInstance,
    DaskTask,
)

_logger = logging.getLogger(__name__)

_DEFAULT_MAX_CPU: Final[float] = 1
_DEFAULT_MAX_RAM: Final[int] = 1024


def get_max_resources_from_dask_task(task: DaskTask) -> Resources:
    return Resources(
        cpus=task.required_resources.get("CPU", _DEFAULT_MAX_CPU),
        ram=task.required_resources.get("RAM", _DEFAULT_MAX_RAM),
    )


def get_task_instance_restriction(task: DaskTask) -> str | None:
    instance_ec2_type: str | None = get_ec2_instance_type_from_resources(
        task.required_resources
    )
    return instance_ec2_type


def _compute_tasks_needed_resources(tasks: list[DaskTask]) -> Resources:
    total = Resources.create_as_empty()
    for t in tasks:
        total += get_max_resources_from_dask_task(t)
    return total


def try_assigning_task_to_node(
    pending_task: DaskTask,
    instance_to_tasks: Iterable[tuple[AssociatedInstance, list[DaskTask]]],
) -> bool:
    for instance, node_assigned_tasks in instance_to_tasks:
        instance_total_resource = instance.ec2_instance.resources
        tasks_needed_resources = _compute_tasks_needed_resources(node_assigned_tasks)
        if (
            instance_total_resource - tasks_needed_resources
        ) >= get_max_resources_from_dask_task(pending_task):
            node_assigned_tasks.append(pending_task)
            return True
    return False


async def try_assigning_task_to_instances(
    app: FastAPI,
    pending_task: DaskTask,
    instances_to_tasks: list[AssignedTasksToInstance],
    *,
    notify_progress: bool,
) -> bool:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    instance_max_time_to_start = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    for assigned_tasks_to_instance in instances_to_tasks:
        tasks_needed_resources = _compute_tasks_needed_resources(
            assigned_tasks_to_instance.assigned_tasks
        )
        if (
            assigned_tasks_to_instance.available_resources - tasks_needed_resources
        ) >= get_max_resources_from_dask_task(pending_task):
            assigned_tasks_to_instance.assigned_tasks.append(pending_task)
            if notify_progress:
                now = datetime.datetime.now(datetime.timezone.utc)
                time_since_launch = (
                    now - assigned_tasks_to_instance.instance.launch_time
                )
                estimated_time_to_completion = (
                    assigned_tasks_to_instance.instance.launch_time
                    + instance_max_time_to_start
                    - now
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
    instance_types_to_tasks: list[AssignedTasksToInstanceType],
) -> bool:
    for assigned_tasks_to_instance_type in instance_types_to_tasks:
        instance_total_resource = Resources(
            cpus=assigned_tasks_to_instance_type.instance_type.cpus,
            ram=assigned_tasks_to_instance_type.instance_type.ram,
        )
        tasks_needed_resources = _compute_tasks_needed_resources(
            assigned_tasks_to_instance_type.assigned_tasks
        )
        if (
            instance_total_resource - tasks_needed_resources
        ) >= get_max_resources_from_dask_task(pending_task):
            assigned_tasks_to_instance_type.assigned_tasks.append(pending_task)
            return True
    return False
