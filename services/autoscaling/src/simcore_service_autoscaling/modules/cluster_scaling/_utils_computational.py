import logging
from typing import Final, cast

from aws_library.ec2 import Resources
from dask_task_models_library.resource_constraints import (
    DaskTaskResources,
    get_ec2_instance_type_from_resources,
)
from pydantic import ByteSize

from ...models import DaskTask

_logger = logging.getLogger(__name__)

_DEFAULT_MAX_CPU: Final[float] = 1
_DEFAULT_MAX_RAM: Final[int] = 1024

_DASK_TO_RESOURCE_NAME_MAPPING: Final[dict[str, str]] = {
    "CPU": "cpus",
    "RAM": "ram",
}
_DEFAULT_DASK_RESOURCES: Final[DaskTaskResources] = DaskTaskResources(
    CPU=_DEFAULT_MAX_CPU, RAM=ByteSize(_DEFAULT_MAX_RAM), threads=1
)


def resources_from_dask_task(task: DaskTask) -> Resources:
    task_resources = (
        _DEFAULT_DASK_RESOURCES | task.required_resources
    )  # merge with defaults to ensure there is always some minimal resource defined

    return Resources.from_flat_dict(
        {
            _DASK_TO_RESOURCE_NAME_MAPPING.get(k, k): cast(int | float | str, v)
            for k, v in task_resources.items()
        }
    )


def get_task_instance_restriction(task: DaskTask) -> str | None:
    instance_ec2_type: str | None = get_ec2_instance_type_from_resources(
        task.required_resources
    )
    return instance_ec2_type
