from typing import Any, TypeAlias

from .constants import DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY

DaskTaskResources: TypeAlias = dict[str, Any]


def create_ec2_resource_constraint_key(ec2_instance_type: str) -> str:
    return f"{DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY}:{ec2_instance_type}"


def get_ec2_instance_type_from_resources(
    task_resources: DaskTaskResources,
) -> str | None:
    for resource_name in task_resources:
        if resource_name.startswith(DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY):
            return resource_name.split(":")[-1]
    return None
