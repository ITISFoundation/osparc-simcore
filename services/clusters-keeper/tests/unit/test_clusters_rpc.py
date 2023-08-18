# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import datetime
from collections.abc import Callable
from typing import Final

import arrow
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from parse import Result, search
from pydantic import parse_obj_as
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import RPCMethodName, RPCNamespace
from simcore_service_clusters_keeper.core.errors import Ec2InstanceNotFoundError
from simcore_service_clusters_keeper.utils.ec2 import HEARTBEAT_TAG_KEY
from types_aiobotocore_ec2 import EC2Client

pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
async def clusters_keeper_rabbitmq_rpc_client(
    rabbitmq_client: Callable[[str], RabbitMQClient]
) -> RabbitMQClient:
    rpc_client = rabbitmq_client("pytest_clusters_keeper_rpc_client")
    assert rpc_client
    await rpc_client.rpc_initialize()
    return rpc_client


CLUSTERS_KEEPER_NAMESPACE: Final[RPCNamespace] = parse_obj_as(
    RPCNamespace, "clusters-keeper"
)


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return faker.pyint(min_value=1)


@pytest.fixture
def _base_configuration(
    docker_swarm: None,
    enabled_rabbitmq: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[str],
    mocked_redis_server: None,
    initialized_app: FastAPI,
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
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
) -> None:
    # send rabbitmq rpc to create_cluster
    rpc_response = await clusters_keeper_rabbitmq_rpc_client.rpc_request(
        CLUSTERS_KEEPER_NAMESPACE,
        RPCMethodName("create_cluster"),
        user_id=user_id,
        wallet_id=wallet_id,
    )
    assert rpc_response
    # wait for response
    # check we do have a new machine in AWS
    await _assert_cluster_instance_created(ec2_client, user_id, wallet_id)


async def test_create_cluster(
    _base_configuration: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
):
    await _create_cluster(
        clusters_keeper_rabbitmq_rpc_client, ec2_client, user_id, wallet_id
    )


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


async def _send_cluster_heartbeat(
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
) -> datetime.datetime:
    rpc_response = await clusters_keeper_rabbitmq_rpc_client.rpc_request(
        CLUSTERS_KEEPER_NAMESPACE,
        RPCMethodName("cluster_heartbeat"),
        user_id=user_id,
        wallet_id=wallet_id,
    )
    assert rpc_response is None

    return await _assert_cluster_heartbeat_on_instance(ec2_client)


async def test_cluster_heartbeat(
    _base_configuration: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
):
    await _create_cluster(
        clusters_keeper_rabbitmq_rpc_client, ec2_client, user_id, wallet_id
    )

    first_heartbeat_time = await _send_cluster_heartbeat(
        clusters_keeper_rabbitmq_rpc_client, ec2_client, user_id, wallet_id
    )

    await asyncio.sleep(1)

    next_heartbeat_time = await _send_cluster_heartbeat(
        clusters_keeper_rabbitmq_rpc_client, ec2_client, user_id, wallet_id
    )

    assert next_heartbeat_time > first_heartbeat_time


async def test_cluster_heartbeat_on_non_existing_cluster_raises(
    _base_configuration: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
):
    with pytest.raises(Ec2InstanceNotFoundError):
        await _send_cluster_heartbeat(
            clusters_keeper_rabbitmq_rpc_client, ec2_client, user_id, wallet_id
        )
