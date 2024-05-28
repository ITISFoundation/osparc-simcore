# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import datetime
from dataclasses import dataclass
from unittest.mock import MagicMock

import arrow
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_clusters_keeper.clusters import OnDemandCluster
from models_library.users import UserID
from models_library.wallets import WalletID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.clusters_keeper.clusters import (
    get_or_create_cluster,
)
from simcore_service_clusters_keeper.utils.ec2 import HEARTBEAT_TAG_KEY
from types_aiobotocore_ec2 import EC2Client

pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return faker.pyint(min_value=1)


@pytest.fixture
def _base_configuration(
    docker_swarm: None,
    enabled_rabbitmq: None,
    mocked_redis_server: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_primary_ec2_instances_envs: EnvVarsDict,
    initialized_app: FastAPI,
    ensure_run_in_sequence_context_is_empty: None,
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


@pytest.fixture
def disable_get_or_create_cluster_caching(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIOCACHE_DISABLE", "1")


@pytest.mark.parametrize("use_wallet_id", [True, False])
async def test_get_or_create_cluster(
    disable_get_or_create_cluster_caching: None,
    _base_configuration: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQRPCClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    use_wallet_id: bool,
    mocked_dask_ping_scheduler: MockedDaskModule,
):
    # send rabbitmq rpc to create_cluster

    rpc_response = await get_or_create_cluster(
        clusters_keeper_rabbitmq_rpc_client,
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
    rpc_response = await get_or_create_cluster(
        clusters_keeper_rabbitmq_rpc_client,
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


async def test_get_or_create_cluster_massive_calls(
    _base_configuration: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQRPCClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    mocked_dask_ping_scheduler: MockedDaskModule,
):
    # NOTE: when a user starts many computational jobs in parallel
    # the get_or_create_cluster is flooded with a lot of calls for the
    # very same cluster (user_id/wallet_id) (e.g. for 256 jobs, that means 256 calls every 5 seconds)
    # that means locking the distributed lock 256 times, then calling AWS API 256 times for the very same information
    # therefore these calls are sequentialized *and* cached! Just sequentializing would make the call last
    # forever otherwise. In effect this creates a rate limiter on this call.
    num_calls = 2000
    results = await asyncio.gather(
        *(
            get_or_create_cluster(
                clusters_keeper_rabbitmq_rpc_client,
                user_id=user_id,
                wallet_id=wallet_id,
            )
            for i in range(num_calls)
        )
    )

    assert results
    assert all(isinstance(response, OnDemandCluster) for response in results)
    mocked_dask_ping_scheduler.ping_scheduler.assert_called_once()
