from typing import Final, Literal, Required, TypedDict

from .constants import DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY

DASK_WORKER_THREAD_RESOURCE_NAME: Final[str] = "threads"


class DaskTaskResources(TypedDict, total=False):
    CPU: Required[float]
    RAM: Required[int]  # in bytes
    # threads is a constant of 1 (enforced by static type checkers via Literal)
    # NOTE: a dask worker can take a task if it has a free thread,
    # regardless of its resources so we need to be careful when interpreting
    # the resources, adding the thread here will mimick this
    threads: Required[Literal[1]]


def create_ec2_resource_constraint_key(ec2_instance_type: str) -> str:
    return f"{DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY}:{ec2_instance_type}"


def get_ec2_instance_type_from_resources(
    task_resources: DaskTaskResources,
) -> str | None:
    for resource_name in task_resources:
        if resource_name.startswith(DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY):
            return resource_name.split(":")[-1]
    return None
