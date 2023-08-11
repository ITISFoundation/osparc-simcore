# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


# Selection of core and tool services started in this swarm fixture (integration)
from collections.abc import Callable
from typing import Final

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from parse import Result, search
from pydantic import parse_obj_as
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import RPCMethodName, RPCNamespace
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


async def test_create_cluster(
    docker_swarm: None,
    enabled_rabbitmq: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[str],
    mocked_redis_server: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    initialized_app: FastAPI,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
):
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
    instances = await ec2_client.describe_instances()
    assert len(instances["Reservations"]) == 1
    assert "Instances" in instances["Reservations"][0]
    assert len(instances["Reservations"][0]["Instances"]) == 1
    assert "Tags" in instances["Reservations"][0]["Instances"][0]
    assert len(instances["Reservations"][0]["Instances"][0]["Tags"]) == 2
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
