# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import datetime
from dataclasses import dataclass
from unittest.mock import MagicMock

import arrow
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE
from models_library.api_schemas_clusters_keeper.clusters import OnDemandCluster
from models_library.users import UserID
from models_library.wallets import WalletID
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient, RPCMethodName
from simcore_service_clusters_keeper.utils.ec2 import HEARTBEAT_TAG_KEY
from types_aiobotocore_ec2 import EC2Client

pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


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


async def _assert_cluster_instance_created(ec2_client: EC2Client) -> None:
    instances = await ec2_client.describe_instances()
    assert len(instances["Reservations"]) == 1
    assert "Instances" in instances["Reservations"][0]
    assert len(instances["Reservations"][0]["Instances"]) == 1


async def _assert_cluster_heartbeat_on_instance(
    ec2_client: EC2Client,
) -> datetime.datetime:
    instances = await ec2_client.describe_instances()
    assert len(instances["Reservations"]) == 1
    assert "Instances" in instances["Reservations"][0]
    assert len(instances["Reservations"][0]["Instances"]) == 1
    assert "Tags" in instances["Reservations"][0]["Instances"][0]
    instance_tags = instances["Reservations"][0]["Instances"][0]["Tags"]
    assert all("Key" in x for x in instance_tags)
    list_of_heartbeats = list(
        filter(lambda x: x["Key"] == HEARTBEAT_TAG_KEY, instance_tags)  # type:ignore
    )
    assert len(list_of_heartbeats) == 1
    assert "Value" in list_of_heartbeats[0]
    this_heartbeat_time = arrow.get(list_of_heartbeats[0]["Value"]).datetime
    assert this_heartbeat_time
    return this_heartbeat_time


@dataclass
class MockedDaskModule:
    ping_scheduler: MagicMock


@pytest.fixture
def mocked_dask_ping_scheduler(mocker: MockerFixture) -> MockedDaskModule:
    return MockedDaskModule(
        ping_scheduler=mocker.patch(
            "simcore_service_clusters_keeper.rpc.clusters.ping_scheduler",
            autospec=True,
            return_value=True,
        ),
    )


@pytest.mark.parametrize("use_wallet_id", [True, False])
async def test_get_or_create_cluster(
    _base_configuration: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQRPCClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    use_wallet_id: bool,
    mocked_dask_ping_scheduler: MockedDaskModule,
):
    # send rabbitmq rpc to create_cluster
    rpc_response = await clusters_keeper_rabbitmq_rpc_client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        RPCMethodName("get_or_create_cluster"),
        user_id=user_id,
        wallet_id=wallet_id if use_wallet_id else None,
    )
    assert rpc_response
    assert isinstance(rpc_response, OnDemandCluster)
    created_cluster = rpc_response
    # check we do have a new machine in AWS
    await _assert_cluster_instance_created(ec2_client)
    # it is called once as moto server creates instances instantly
    mocked_dask_ping_scheduler.ping_scheduler.assert_called_once()
    mocked_dask_ping_scheduler.ping_scheduler.reset_mock()

    # calling it again returns the existing cluster
    rpc_response = await clusters_keeper_rabbitmq_rpc_client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        RPCMethodName("get_or_create_cluster"),
        user_id=user_id,
        wallet_id=wallet_id if use_wallet_id else None,
    )
    assert rpc_response
    assert isinstance(rpc_response, OnDemandCluster)
    returned_cluster = rpc_response
    # check we still have only 1 instance
    await _assert_cluster_heartbeat_on_instance(ec2_client)
    mocked_dask_ping_scheduler.ping_scheduler.assert_called_once()

    assert created_cluster == returned_cluster
