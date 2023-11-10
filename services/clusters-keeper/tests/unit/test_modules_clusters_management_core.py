# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import Awaitable, Callable
from typing import Final
from unittest.mock import MagicMock

import pytest
from attr import dataclass
from faker import Faker
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_clusters_keeper.models import EC2InstanceData
from simcore_service_clusters_keeper.modules.clusters import (
    cluster_heartbeat,
    create_cluster,
)
from simcore_service_clusters_keeper.modules.clusters_management_core import (
    check_clusters,
)
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture(params=("with_wallet", "without_wallet"))
def wallet_id(faker: Faker, request: pytest.FixtureRequest) -> WalletID | None:
    return faker.pyint(min_value=1) if request.param == "with_wallet" else None


_FAST_TIME_BEFORE_TERMINATION_SECONDS: Final[int] = 10


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # fast interval
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "CLUSTERS_KEEPER_MAX_MISSED_HEARTBEATS_BEFORE_CLUSTER_TERMINATION": "1",
            "SERVICE_TRACKING_HEARTBEAT": f"{_FAST_TIME_BEFORE_TERMINATION_SECONDS}",
        },
    )


@pytest.fixture
def _base_configuration(
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names_env: list[str],
    disabled_rabbitmq: None,
    mocked_redis_server: None,
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


async def _assert_instances_state(
    ec2_client: EC2Client, *, instance_ids: list[str], state: InstanceStateNameType
) -> None:
    described_instances = await ec2_client.describe_instances(InstanceIds=instance_ids)
    assert described_instances
    assert "Reservations" in described_instances

    for reservation in described_instances["Reservations"]:
        assert "Instances" in reservation

        for instance in reservation["Instances"]:
            assert "State" in instance
            assert "Name" in instance["State"]
            assert instance["State"]["Name"] == state


@dataclass
class MockedDaskModule:
    ping_scheduler: MagicMock
    is_scheduler_busy: MagicMock


@pytest.fixture
def mocked_dask_ping_scheduler(mocker: MockerFixture) -> MockedDaskModule:
    return MockedDaskModule(
        ping_scheduler=mocker.patch(
            "simcore_service_clusters_keeper.modules.clusters_management_core.ping_scheduler",
            autospec=True,
            return_value=True,
        ),
        is_scheduler_busy=mocker.patch(
            "simcore_service_clusters_keeper.modules.clusters_management_core.is_scheduler_busy",
            autospec=True,
            return_value=True,
        ),
    )


async def test_cluster_management_core_properly_removes_unused_instances(
    disable_clusters_management_background_task: None,
    _base_configuration: None,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID | None,
    initialized_app: FastAPI,
    mocked_dask_ping_scheduler: MockedDaskModule,
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
    mocked_dask_ping_scheduler.ping_scheduler.assert_called_once()
    mocked_dask_ping_scheduler.ping_scheduler.reset_mock()
    mocked_dask_ping_scheduler.is_scheduler_busy.assert_called_once()
    mocked_dask_ping_scheduler.is_scheduler_busy.reset_mock()

    # running the cluster management task after the heartbeat came in shall not remove anything
    await asyncio.sleep(_FAST_TIME_BEFORE_TERMINATION_SECONDS + 1)
    await cluster_heartbeat(initialized_app, user_id=user_id, wallet_id=wallet_id)
    await check_clusters(initialized_app)
    await _assert_cluster_exist_and_state(
        ec2_client, instances=created_clusters, state="running"
    )
    mocked_dask_ping_scheduler.ping_scheduler.assert_called_once()
    mocked_dask_ping_scheduler.ping_scheduler.reset_mock()
    mocked_dask_ping_scheduler.is_scheduler_busy.assert_called_once()
    mocked_dask_ping_scheduler.is_scheduler_busy.reset_mock()

    # after waiting the termination time, running the task shall remove the cluster
    await asyncio.sleep(_FAST_TIME_BEFORE_TERMINATION_SECONDS + 1)
    await check_clusters(initialized_app)
    await _assert_cluster_exist_and_state(
        ec2_client, instances=created_clusters, state="terminated"
    )
    mocked_dask_ping_scheduler.ping_scheduler.assert_called_once()
    mocked_dask_ping_scheduler.is_scheduler_busy.assert_called_once()


async def test_cluster_management_core_properly_removes_workers_on_shutdown(
    disable_clusters_management_background_task: None,
    _base_configuration: None,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID | None,
    initialized_app: FastAPI,
    mocked_dask_ping_scheduler: MockedDaskModule,
    create_ec2_workers: Callable[[int], Awaitable[list[str]]],
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
    mocked_dask_ping_scheduler.ping_scheduler.assert_called_once()
    mocked_dask_ping_scheduler.ping_scheduler.reset_mock()
    mocked_dask_ping_scheduler.is_scheduler_busy.assert_called_once()
    mocked_dask_ping_scheduler.is_scheduler_busy.reset_mock()

    # create some workers
    worker_instance_ids = await create_ec2_workers(10)
    await _assert_instances_state(
        ec2_client, instance_ids=worker_instance_ids, state="running"
    )
    # after waiting the termination time, running the task shall remove the cluster
    await asyncio.sleep(_FAST_TIME_BEFORE_TERMINATION_SECONDS + 1)
    await check_clusters(initialized_app)
    await _assert_cluster_exist_and_state(
        ec2_client, instances=created_clusters, state="terminated"
    )
    mocked_dask_ping_scheduler.ping_scheduler.assert_called_once()
    mocked_dask_ping_scheduler.is_scheduler_busy.assert_called_once()
    # check workers were also terminated
    await _assert_instances_state(
        ec2_client, instance_ids=worker_instance_ids, state="terminated"
    )
