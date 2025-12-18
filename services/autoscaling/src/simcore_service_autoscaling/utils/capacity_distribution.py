import collections

from aws_library.ec2._errors import EC2TooManyInstancesError
from aws_library.ec2._models import EC2InstanceType, EC2Tags
from fastapi import FastAPI

from ..models import InstanceToLaunch
from ..modules.ec2 import get_ec2_client
from ..modules.ssm import get_application_settings


def _cap_instances_minimal(
    needed_instances: dict[InstanceToLaunch, int],
    max_instances: int,
) -> dict[InstanceToLaunch, int]:
    """Caps to at most 1 instance per batch when capacity is too low.

    Returns a dict with at most max_instances batches, each with count=1.
    """
    capped_instances: dict[InstanceToLaunch, int] = {}
    for idx, instance_batch in enumerate(needed_instances.keys()):
        if (idx + 1) > max_instances:
            break
        capped_instances[instance_batch] = 1
    return capped_instances


def _fill_capacity_round_robin(
    needed_by_type: collections.Counter[EC2InstanceType],
    max_instances: int,
) -> collections.Counter[EC2InstanceType]:
    """Distributes capacity across instance types using round-robin.

    Starts with 1 per type, then increases round-robin until max_instances reached.
    """
    capped_by_type = collections.Counter(dict.fromkeys(needed_by_type, 1))

    while capped_by_type.total() < max_instances:
        for instance_type in needed_by_type:
            if capped_by_type.total() == max_instances:
                break
            if needed_by_type[instance_type] > capped_by_type[instance_type]:
                capped_by_type[instance_type] += 1

    return capped_by_type


def _distribute_capped_counts_proportionally(
    needed_instances: dict[InstanceToLaunch, int],
    needed_by_type: collections.Counter[EC2InstanceType],
    capped_by_type: collections.Counter[EC2InstanceType],
    max_instances: int,
) -> dict[InstanceToLaunch, int]:
    """Distributes capped type counts back to label batches proportionally.

    If a type needs 10 instances but is capped to 5, each batch of that type
    gets proportionally reduced. Handles rounding errors by distributing remainder.
    """
    result: dict[InstanceToLaunch, int] = {}
    for instance_batch, original_count in needed_instances.items():
        instance_type = instance_batch.instance_type
        capped_total = capped_by_type[instance_type]
        original_total = needed_by_type[instance_type]
        assert original_total > 0  # nosec

        proportional_count = int(original_count * capped_total / original_total)
        if proportional_count > 0:
            result[instance_batch] = proportional_count

    # Handle rounding errors - distribute remaining instances
    remaining = max_instances - sum(result.values())
    for instance_batch in needed_instances:
        if remaining == 0:
            break
        if instance_batch in result:
            result[instance_batch] += 1
            remaining -= 1

    return result


async def cap_needed_instances(
    app: FastAPI, needed_instances: dict[InstanceToLaunch, int], ec2_tags: EC2Tags
) -> dict[InstanceToLaunch, int]:
    """Caps the needed instances dict[InstanceToLaunch, int] to the maximal allowed number of instances.

    Uses proportional distribution when capping is needed - if we need 10 instances of a type but can only
    create 5, each batch with that type gets proportionally reduced.

    NOTE: the maximum allowed number of instances contains the current number of running/pending machines

    Raises:
        Ec2TooManyInstancesError: raised when the maximum of machines is already running/pending
    """
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    current_instances = await ec2_client.get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=ec2_tags,
    )
    current_number_of_instances = len(current_instances)
    # 1. Check current capacity, raise if already at max
    if (
        current_number_of_instances
        >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ):
        raise EC2TooManyInstancesError(
            num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
        )

    # 2. Check if needed instances fit, otherwise cap proportionally
    total_number_of_needed_instances = sum(needed_instances.values())
    if (
        current_number_of_instances + total_number_of_needed_instances
        <= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ):
        # ok that fits no need to do anything here
        return needed_instances

    # 3. we need to cap
    max_number_of_creatable_instances = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
        - current_number_of_instances
    )

    # Aggregate by instance type
    needed_by_type = collections.Counter(
        {
            instance_batch.instance_type: count
            for instance_batch, count in needed_instances.items()
        }
    )

    # Early exit if we can't even create 1 of each type
    if max_number_of_creatable_instances < len(needed_by_type):
        return _cap_instances_minimal(
            needed_instances, max_number_of_creatable_instances
        )

    # Distribute capacity across types using round-robin
    capped_by_type = _fill_capacity_round_robin(
        needed_by_type, max_number_of_creatable_instances
    )

    # Distribute capped type counts back to label batches proportionally
    return _distribute_capped_counts_proportionally(
        needed_instances,
        needed_by_type,
        capped_by_type,
        max_number_of_creatable_instances,
    )
