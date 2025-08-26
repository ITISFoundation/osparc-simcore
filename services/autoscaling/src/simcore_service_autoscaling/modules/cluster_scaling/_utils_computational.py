import logging
from typing import Final

from aws_library.ec2 import Resources
from dask_task_models_library.resource_constraints import (
    get_ec2_instance_type_from_resources,
)

from ...models import DaskTask

_logger = logging.getLogger(__name__)

_DEFAULT_MAX_CPU: Final[float] = 1
_DEFAULT_MAX_RAM: Final[int] = 1024


def resources_from_dask_task(task: DaskTask) -> Resources:
    return Resources(
        cpus=task.required_resources.get("CPU", _DEFAULT_MAX_CPU),
        ram=task.required_resources.get("RAM", _DEFAULT_MAX_RAM),
    )


def get_task_instance_restriction(task: DaskTask) -> str | None:
    instance_ec2_type: str | None = get_ec2_instance_type_from_resources(
        task.required_resources
    )
    return instance_ec2_type
