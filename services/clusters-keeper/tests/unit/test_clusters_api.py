# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import datetime

import arrow
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from parse import Result, search
from simcore_service_clusters_keeper.clusters_api import (
    cluster_heartbeat,
    create_cluster,
    delete_clusters,
)
from simcore_service_clusters_keeper.core.errors import Ec2InstanceNotFoundError
from simcore_service_clusters_keeper.models import EC2InstanceData
from simcore_service_clusters_keeper.utils.ec2 import HEARTBEAT_TAG_KEY
from types_aiobotocore_ec2 import EC2Client


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return faker.pyint(min_value=1)


@pytest.fixture
def _base_configuration(
    docker_swarm: None,
    disabled_rabbitmq: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[str],
    mocked_redis_server: None,
) -> None:
    ...


async def _assert_cluster_instance_created(
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    instances = await ec2_client.describe_instances()
    assert len(instances["Reservations"]) == 1
    assert "Instances" in instances["Reservations"][0]
    assert len(instances["Reservations"][0]["Instances"]) == 1
    assert "Tags" in instances["Reservations"][0]["Instances"][0]
    instance_ec2_tags = instances["Reservations"][0]["Instances"][0]["Tags"]
    assert len(instance_ec2_tags) == 4
    assert all("Key" in x for x in instance_ec2_tags)
    assert all("Value" in x for x in instance_ec2_tags)

    assert "Key" in instances["Reservations"][0]["Instances"][0]["Tags"][0]
    assert (
        instances["Reservations"][0]["Instances"][0]["Tags"][0]["Key"]
        == "io.simcore.clusters-keeper.version"
    )
    assert "Key" in instances["Reservations"][0]["Instances"][0]["Tags"][1]
    assert instances["Reservations"][0]["Instances"][0]["Tags"][1]["Key"] == "Name"
    assert "Value" in instances["Reservations"][0]["Instances"][0]["Tags"][1]
    instance_name = instances["Reservations"][0]["Instances"][0]["Tags"][1]["Value"]

    parse_result = search("user_id:{user_id:d}-wallet_id:{wallet_id:d}", instance_name)
    assert isinstance(parse_result, Result)
    assert parse_result["user_id"] == user_id
    assert parse_result["wallet_id"] == wallet_id


async def _create_cluster(
    app: FastAPI,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
) -> list[EC2InstanceData]:
    created_clusters = await create_cluster(app, user_id=user_id, wallet_id=wallet_id)
    assert len(created_clusters) == 1
    # check we do have a new machine in AWS
    await _assert_cluster_instance_created(ec2_client, user_id, wallet_id)
    return created_clusters


async def test_create_cluster(
    _base_configuration: None,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    initialized_app: FastAPI,
):
    await _create_cluster(initialized_app, ec2_client, user_id, wallet_id)


async def _assert_cluster_heartbeat_on_instance(
    ec2_client: EC2Client,
) -> datetime.datetime:
    instances = await ec2_client.describe_instances()
    assert len(instances["Reservations"]) == 1
    assert "Instances" in instances["Reservations"][0]
    assert len(instances["Reservations"][0]["Instances"]) == 1
    assert "Tags" in instances["Reservations"][0]["Instances"][0]
    instance_tags = instances["Reservations"][0]["Instances"][0]["Tags"]
    assert len(instance_tags) == 5
    assert all("Key" in x for x in instance_tags)
    list_of_heartbeats = list(
        filter(lambda x: x["Key"] == HEARTBEAT_TAG_KEY, instance_tags)  # type:ignore
    )
    assert len(list_of_heartbeats) == 1
    assert "Value" in list_of_heartbeats[0]
    this_heartbeat_time = arrow.get(list_of_heartbeats[0]["Value"]).datetime
    assert this_heartbeat_time
    return this_heartbeat_time


async def test_cluster_heartbeat(
    _base_configuration: None,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    initialized_app: FastAPI,
):
    await _create_cluster(initialized_app, ec2_client, user_id, wallet_id)

    await cluster_heartbeat(initialized_app, user_id=user_id)
    first_heartbeat_time = await _assert_cluster_heartbeat_on_instance(ec2_client)

    await asyncio.sleep(1)

    await cluster_heartbeat(initialized_app, user_id=user_id)
    next_heartbeat_time = await _assert_cluster_heartbeat_on_instance(ec2_client)

    assert next_heartbeat_time > first_heartbeat_time


async def test_cluster_heartbeat_on_non_existing_cluster_raises(
    _base_configuration: None,
    ec2_client: EC2Client,
    user_id: UserID,
    initialized_app: FastAPI,
):
    with pytest.raises(Ec2InstanceNotFoundError):
        await cluster_heartbeat(initialized_app, user_id=user_id)


async def _assert_all_clusters_terminated(
    ec2_client: EC2Client,
) -> None:
    described_instances = await ec2_client.describe_instances()
    if "Reservations" not in described_instances:
        print("no reservations on AWS. ok.")
        return

    for reservation in described_instances["Reservations"]:
        if "Instances" not in reservation:
            print("no instance in reservation on AWS, weird but ok.")
            continue

        for instance in reservation["Instances"]:
            assert "State" in instance
            assert "Name" in instance["State"]
            assert instance["State"]["Name"] == "terminated"


async def test_delete_cluster(
    _base_configuration: None,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    initialized_app: FastAPI,
):
    created_instances = await _create_cluster(
        initialized_app, ec2_client, user_id, wallet_id
    )
    await delete_clusters(initialized_app, instances=created_instances)
    await _assert_all_clusters_terminated(ec2_client)
