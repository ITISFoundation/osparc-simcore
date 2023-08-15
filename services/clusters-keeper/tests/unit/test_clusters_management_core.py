# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from typing import Final

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_clusters_keeper.clusters_api import (
    cluster_heartbeat,
    create_cluster,
)
from simcore_service_clusters_keeper.clusters_management_core import check_clusters
from simcore_service_clusters_keeper.models import EC2InstanceData
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return faker.pyint(min_value=1)


_FAST_TIME_BEFORE_TERMINATION_SECONDS: Final[int] = 10


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # fast interval
    monkeypatch.setenv(
        "EC2_INSTANCES_TIME_BEFORE_TERMINATION",
        f"{_FAST_TIME_BEFORE_TERMINATION_SECONDS}",
    )
    app_environment[
        "EC2_INSTANCES_TIME_BEFORE_TERMINATION"
    ] = f"{_FAST_TIME_BEFORE_TERMINATION_SECONDS}"
    return app_environment


@pytest.fixture
def _base_configuration(
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[str],
) -> None:
    ...


async def _assert_cluster_exist_and_state(
    ec2_client: EC2Client,
    *,
    instances: list[EC2InstanceData],
    state: InstanceStateNameType,
) -> None:
    described_instances = await ec2_client.describe_instances(
        InstanceIds=[i.id for i in instances]
    )
    assert described_instances
    assert "Reservations" in described_instances

    for reservation in described_instances["Reservations"]:
        assert "Instances" in reservation

        for instance in reservation["Instances"]:
            assert "State" in instance
            assert "Name" in instance["State"]
            assert instance["State"]["Name"] == state


async def test_cluster_management_core_properly_unused_instances(
    disable_clusters_management_background_task: None,
    _base_configuration: None,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    initialized_app: FastAPI,
):
    created_clusters = await create_cluster(
        initialized_app, user_id=user_id, wallet_id=wallet_id
    )
    assert len(created_clusters) == 1

    # running the cluster management task shall not remove anything
    await check_clusters(initialized_app)
    await _assert_cluster_exist_and_state(
        ec2_client, instances=created_clusters, state="running"
    )

    # running the cluster management task after the heartbeat came in shall not remove anything
    await asyncio.sleep(_FAST_TIME_BEFORE_TERMINATION_SECONDS + 1)
    await cluster_heartbeat(initialized_app, user_id=user_id)
    await check_clusters(initialized_app)
    await _assert_cluster_exist_and_state(
        ec2_client, instances=created_clusters, state="running"
    )

    # after waiting the termination time, running the task shall remove the cluster
    await asyncio.sleep(_FAST_TIME_BEFORE_TERMINATION_SECONDS + 1)
    await check_clusters(initialized_app)
    await _assert_cluster_exist_and_state(
        ec2_client, instances=created_clusters, state="terminated"
    )
