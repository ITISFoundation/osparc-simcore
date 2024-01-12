import datetime
import logging

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Task
from servicelib.utils_formatting import timedelta_as_minute_second

from ..core.settings import get_application_settings
from ..models import AssignedTasksToInstance, AssignedTasksToInstanceType
from . import utils_docker
from .rabbitmq import log_tasks_message, progress_tasks_message

logger = logging.getLogger(__name__)


def try_assigning_task_to_instance_types(
    task: Task,
    instance_types_to_tasks: list[AssignedTasksToInstanceType],
) -> bool:
    task_required_resources = utils_docker.get_max_resources_from_docker_task(task)
    for assigned_tasks_to_instance_type in instance_types_to_tasks:
        if assigned_tasks_to_instance_type.has_resources_for_task(
            task_required_resources
        ):
            assigned_tasks_to_instance_type.assign_task(task)
            return True
    return False


async def try_assigning_task_to_instances(
    app: FastAPI,
    task: Task,
    instances_to_tasks: list[AssignedTasksToInstance],
    *,
    notify_progress: bool,
) -> bool:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    instance_max_time_to_start = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    task_required_resources = utils_docker.get_max_resources_from_docker_task(task)
    for assigned_tasks_to_instance in instances_to_tasks:
        if assigned_tasks_to_instance.has_resources_for_task(task_required_resources):
            assigned_tasks_to_instance.assign_task(task, task_required_resources)
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

                await log_tasks_message(
                    app,
                    [task],
                    f"adding machines to the cluster (time waiting: {timedelta_as_minute_second(time_since_launch)}, "
                    f"est. remaining time: {timedelta_as_minute_second(estimated_time_to_completion)})...please wait...",
                )
                await progress_tasks_message(
                    app,
                    [task],
                    time_since_launch.total_seconds()
                    / instance_max_time_to_start.total_seconds(),
                )
            return True
    return False
