import json
from typing import Final

import boto3
from aiocache import cached
from mypy_boto3_ec2 import EC2ServiceResource
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from mypy_boto3_ec2.type_defs import FilterTypeDef

from .models import AppState
from .utils import get_instance_name, to_async


@to_async
def _list_running_ec2_instances(
    ec2_resource: EC2ServiceResource,
    key_name: str,
    custom_tags: dict[str, str],
    user_id: int | None,
    wallet_id: int | None,
    instance_id: str | None,
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
    if instance_id:
        ec2_filters.append({"Name": "instance-id", "Values": [f"{instance_id}"]})
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
    return await _list_running_ec2_instances(
        state.ec2_resource_clusters_keeper,
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        user_id,
        wallet_id,
        None,
    )


async def list_dynamic_instances_from_ec2(
    state: AppState,
    *,
    user_id: int | None,
    wallet_id: int | None,
    instance_id: str | None,
) -> ServiceResourceInstancesCollection:
    assert state.environment["EC2_INSTANCES_KEY_NAME"]
    custom_tags = {}
    if state.environment["EC2_INSTANCES_CUSTOM_TAGS"]:
        custom_tags = json.loads(state.environment["EC2_INSTANCES_CUSTOM_TAGS"])
    assert state.ec2_resource_autoscaling
    return await _list_running_ec2_instances(
        state.ec2_resource_autoscaling,
        state.environment["EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        user_id,
        wallet_id,
        instance_id,
    )


_DEFAULT_BASTION_NAME: Final[str] = "bastion-host"


@cached()
async def get_computational_bastion_instance(state: AppState) -> Instance:
    assert state.ec2_resource_clusters_keeper  # nosec
    assert state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"]  # nosec
    instances = await _list_running_ec2_instances(
        state.ec2_resource_clusters_keeper,
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"],
        {},
        None,
        None,
        None,
    )

    possible_bastions = list(
        filter(lambda i: _DEFAULT_BASTION_NAME in get_instance_name(i), instances)
    )
    assert len(possible_bastions) == 1
    return possible_bastions[0]


@cached()
async def get_dynamic_bastion_instance(state: AppState) -> Instance:
    assert state.ec2_resource_autoscaling  # nosec
    assert state.environment["EC2_INSTANCES_KEY_NAME"]  # nosec
    instances = await _list_running_ec2_instances(
        state.ec2_resource_autoscaling,
        state.environment["EC2_INSTANCES_KEY_NAME"],
        {},
        None,
        None,
        None,
    )

    possible_bastions = list(
        filter(lambda i: _DEFAULT_BASTION_NAME in get_instance_name(i), instances)
    )
    assert len(possible_bastions) == 1
    return possible_bastions[0]


def cluster_keeper_region(state: AppState) -> str:
    assert state.environment["CLUSTERS_KEEPER_EC2_REGION_NAME"]  # nosec
    return state.environment["CLUSTERS_KEEPER_EC2_REGION_NAME"]


def autoscaling_region(state: AppState) -> str:
    assert state.environment["AUTOSCALING_EC2_REGION_NAME"]  # nosec
    return state.environment["AUTOSCALING_EC2_REGION_NAME"]


async def get_bastion_instance_from_remote_instance(
    state: AppState, remote_instance: Instance
) -> Instance:
    availability_zone = remote_instance.placement["AvailabilityZone"]
    if cluster_keeper_region(state) in availability_zone:
        return await get_computational_bastion_instance(state)
    if autoscaling_region(state) in availability_zone:
        return await get_dynamic_bastion_instance(state)
    msg = "no corresponding bastion instance!"
    raise RuntimeError(msg)


def cluster_keeper_ec2_client(state: AppState) -> EC2ServiceResource:
    return boto3.resource(
        "ec2",
        region_name=cluster_keeper_region(state),
        aws_access_key_id=state.environment["CLUSTERS_KEEPER_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=state.environment[
            "CLUSTERS_KEEPER_EC2_SECRET_ACCESS_KEY"
        ],
    )


def autoscaling_ec2_client(state: AppState) -> EC2ServiceResource:
    return boto3.resource(
        "ec2",
        region_name=autoscaling_region(state),
        aws_access_key_id=state.environment["AUTOSCALING_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=state.environment["AUTOSCALING_EC2_SECRET_ACCESS_KEY"],
    )
