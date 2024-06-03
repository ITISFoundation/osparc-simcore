import asyncio
import json

from mypy_boto3_ec2 import EC2ServiceResource
from mypy_boto3_ec2.service_resource import ServiceResourceInstancesCollection
from mypy_boto3_ec2.type_defs import FilterTypeDef

from .models import AppState


def _list_running_ec2_instances(
    ec2_resource: EC2ServiceResource,
    key_name: str,
    custom_tags: dict[str, str],
    user_id: int | None,
    wallet_id: int | None,
) -> ServiceResourceInstancesCollection:
    # get all the running instances

    ec2_filters: list[FilterTypeDef] = [
        {"Name": "instance-state-name", "Values": ["running", "pending"]},
        {"Name": "key-name", "Values": [key_name]},
    ]
    if custom_tags:
        ec2_filters.extend(
            [
                {"Name": f"tag:{key}", "Values": [f"{value}"]}
                for key, value in custom_tags.items()
            ]
        )

    if user_id:
        ec2_filters.append({"Name": "tag:user_id", "Values": [f"{user_id}"]})
    if wallet_id:
        ec2_filters.append({"Name": "tag:wallet_id", "Values": [f"{wallet_id}"]})

    return ec2_resource.instances.filter(Filters=ec2_filters)


async def list_computational_instances_from_ec2(
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
) -> ServiceResourceInstancesCollection:
    assert state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"]
    assert state.environment["WORKERS_EC2_INSTANCES_KEY_NAME"]
    assert (
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"]
        == state.environment["WORKERS_EC2_INSTANCES_KEY_NAME"]
    ), "key name is different on primary and workers. TIP: adjust this code now"
    custom_tags = {}
    if state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"]:
        assert (
            state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"]
            == state.environment["WORKERS_EC2_INSTANCES_CUSTOM_TAGS"]
        ), "custom tags are different on primary and workers. TIP: adjust this code now"
        custom_tags = json.loads(state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"])
    assert state.ec2_resource_clusters_keeper
    return await asyncio.get_event_loop().run_in_executor(
        None,
        _list_running_ec2_instances,
        state.ec2_resource_clusters_keeper,
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        user_id,
        wallet_id,
    )


async def list_dynamic_instances_from_ec2(
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
) -> ServiceResourceInstancesCollection:
    assert state.environment["EC2_INSTANCES_KEY_NAME"]
    custom_tags = {}
    if state.environment["EC2_INSTANCES_CUSTOM_TAGS"]:
        custom_tags = json.loads(state.environment["EC2_INSTANCES_CUSTOM_TAGS"])
    assert state.ec2_resource_autoscaling
    return await asyncio.get_event_loop().run_in_executor(
        None,
        _list_running_ec2_instances,
        state.ec2_resource_autoscaling,
        state.environment["EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        user_id,
        wallet_id,
    )
