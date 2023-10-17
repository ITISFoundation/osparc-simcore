import datetime
import logging

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Task
from servicelib.utils_formatting import timedelta_as_minute_second

from ..core.settings import get_application_settings
from ..models import AssociatedInstance, EC2InstanceData, EC2InstanceType, Resources
from . import utils_docker
from .rabbitmq import log_tasks_message, progress_tasks_message

logger = logging.getLogger(__name__)


def try_assigning_task_to_node(
    pending_task: Task, instance_to_tasks: list[tuple[AssociatedInstance, list[Task]]]
) -> bool:
    for instance, node_assigned_tasks in instance_to_tasks:
        instance_total_resource = utils_docker.get_node_total_resources(instance.node)
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            node_assigned_tasks
        )
        if (
            instance_total_resource - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            node_assigned_tasks.append(pending_task)
            return True
    return False


def try_assigning_task_to_instances(
    pending_task: Task,
    list_of_instance_to_tasks: list[tuple[EC2InstanceType, list[Task]]],
) -> bool:
    for instance, instance_assigned_tasks in list_of_instance_to_tasks:
        instance_total_resource = Resources(cpus=instance.cpus, ram=instance.ram)
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            instance_assigned_tasks
        )
        if (
            instance_total_resource - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            instance_assigned_tasks.append(pending_task)
            return True
    return False


async def try_assigning_task_to_pending_instances(
    app: FastAPI,
    pending_task: Task,
    list_of_instances_to_tasks: list[tuple[EC2InstanceData, list[Task]]],
    type_to_instance_map: dict[str, EC2InstanceType],
    *,
    notify_progress: bool,
) -> bool:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    instance_max_time_to_start = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    for instance, instance_assigned_tasks in list_of_instances_to_tasks:
        instance_type = type_to_instance_map[instance.type]
        instance_total_resources = Resources(
            cpus=instance_type.cpus, ram=instance_type.ram
        )
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            instance_assigned_tasks
        )
        if (
            instance_total_resources - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            instance_assigned_tasks.append(pending_task)
            if notify_progress:
                now = datetime.datetime.now(datetime.timezone.utc)
                time_since_launch = now - instance.launch_time
                estimated_time_to_completion = (
                    instance.launch_time + instance_max_time_to_start - now
                )

                await log_tasks_message(
                    app,
                    [pending_task],
                    f"adding machines to the cluster (time waiting: {timedelta_as_minute_second(time_since_launch)}, "
                    f"est. remaining time: {timedelta_as_minute_second(estimated_time_to_completion)})...please wait...",
                )
                await progress_tasks_message(
                    app,
                    [pending_task],
                    time_since_launch.total_seconds()
                    / instance_max_time_to_start.total_seconds(),
                )
            return True
    return False
