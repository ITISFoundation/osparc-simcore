# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from faker import Faker
from fastapi import FastApi
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_clusters_keeper.clusters_api import create_cluster
from simcore_service_clusters_keeper.clusters_management_core import check_clusters
from types_aiobotocore_ec2 import EC2Client


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
    mocked_aws_server_envs: None,
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


async def test_cluster_management_core_properly_unused_instances(
    disable_clusters_management_background_task: None,
    _base_configuration: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    initialized_app: FastApi,
):
    created_clusters = await create_cluster(
        initialized_app, user_id=user_id, wallet_id=wallet_id
    )
    assert len(created_clusters) == 1

    # running the cluster management task shall not remove anything
    await check_clusters(initialized_app)
    _assert_cluster_exists()

    # running the cluster management task after the heartbeat came in shall not remove anything
    await asyncio.sleep(_FAST_TIME_BEFORE_TERMINATION_SECONDS + 1)
    await cluster_heartbeat()
    await check_clusters(initialized_app)
    _assert_cluster_exists()

    # after waiting the termination time, running the task shall remove the cluster
    await asyncio.sleep(_FAST_TIME_BEFORE_TERMINATION_SECONDS + 1)
    await check_clusters(initialized_app)
    _assert_cluster_does_not_exists()
