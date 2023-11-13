# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import importlib.resources
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import aiodocker
import httpx
import pytest
import requests
import simcore_service_clusters_keeper
import simcore_service_clusters_keeper.data
import yaml
from aiohttp.test_utils import unused_port
from asgi_lifespan import LifespanManager
from faker import Faker
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from moto.server import ThreadedMotoServer
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_host import get_localhost_ip
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from simcore_service_clusters_keeper.core.application import create_app
from simcore_service_clusters_keeper.core.settings import (
    ApplicationSettings,
    EC2ClustersKeeperSettings,
)
from simcore_service_clusters_keeper.modules.ec2 import ClustersKeeperEC2
from simcore_service_clusters_keeper.utils.ec2 import get_cluster_name
from types_aiobotocore_ec2.client import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType

pytest_plugins = [
    "pytest_simcore.dask_scheduler",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "clusters_keeper"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_clusters_keeper"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_clusters_keeper.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def ec2_instances() -> list[InstanceTypeType]:
    # these are some examples
    return ["t2.nano", "m5.12xlarge"]


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    ec2_instances: list[InstanceTypeType],
) -> EnvVarsDict:
    # SEE https://faker.readthedocs.io/en/master/providers/faker.providers.internet.html?highlight=internet#faker-providers-internet
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "CLUSTERS_KEEPER_EC2_ACCESS": "{}",
            "EC2_CLUSTERS_KEEPER_ACCESS_KEY_ID": faker.pystr(),
            "EC2_CLUSTERS_KEEPER_SECRET_ACCESS_KEY": faker.pystr(),
            "CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES": "{}",
            "PRIMARY_EC2_INSTANCES_KEY_NAME": faker.pystr(),
            "PRIMARY_EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "PRIMARY_EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "PRIMARY_EC2_INSTANCES_AMI_ID": faker.pystr(),
            "PRIMARY_EC2_INSTANCES_ALLOWED_TYPES": json.dumps(ec2_instances),
            "CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES": "{}",
            "WORKERS_EC2_INSTANCES_ALLOWED_TYPES": json.dumps(ec2_instances),
            "WORKERS_EC2_INSTANCES_AMI_ID": faker.pystr(),
            "WORKERS_EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "WORKERS_EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "WORKERS_EC2_INSTANCES_KEY_NAME": faker.pystr(),
        },
    )
    return mock_env_devel_environment | envs


@pytest.fixture
def disable_clusters_management_background_task(
    mocker: MockerFixture,
) -> Iterator[None]:
    start_background_task = mocker.patch(
        "simcore_service_clusters_keeper.modules.clusters_management_task.start_periodic_task",
        autospec=True,
    )

    stop_background_task = mocker.patch(
        "simcore_service_clusters_keeper.modules.clusters_management_task.stop_periodic_task",
        autospec=True,
    )

    yield

    start_background_task.assert_called_once()
    stop_background_task.assert_called_once()


@pytest.fixture
def disabled_rabbitmq(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("RABBIT_HOST")
    monkeypatch.delenv("RABBIT_USER")
    monkeypatch.delenv("RABBIT_SECURE")
    monkeypatch.delenv("RABBIT_PASSWORD")


@pytest.fixture
def disabled_ec2(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLUSTERS_KEEPER_EC2_ACCESS", "null")


@pytest.fixture
def enabled_rabbitmq(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitSettings:
    return rabbit_service


@pytest.fixture
async def initialized_app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app, shutdown_timeout=20):
        yield app


@pytest.fixture
def app_settings(initialized_app: FastAPI) -> ApplicationSettings:
    assert initialized_app.state.settings
    return initialized_app.state.settings


@pytest.fixture
async def async_client(initialized_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url=f"http://{initialized_app.title}.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture(scope="module")
def mocked_aws_server() -> Iterator[ThreadedMotoServer]:
    """creates a moto-server that emulates AWS services in place
    NOTE: Never use a bucket with underscores it fails!!
    """
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=unused_port())
    # pylint: disable=protected-access
    print(
        f"--> started mock AWS server on {server._ip_address}:{server._port}"  # noqa: SLF001
    )
    print(
        f"--> Dashboard available on [http://{server._ip_address}:{server._port}/moto-api/]"  # noqa: SLF001
    )
    server.start()
    yield server
    server.stop()
    print(
        f"<-- stopped mock AWS server on {server._ip_address}:{server._port}"  # noqa: SLF001
    )


@pytest.fixture
def reset_aws_server_state(mocked_aws_server: ThreadedMotoServer) -> Iterator[None]:
    # NOTE: reset_aws_server_state [http://docs.getmoto.org/en/latest/docs/server_mode.html#reset-api]
    yield
    # pylint: disable=protected-access
    requests.post(
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}/moto-api/reset",  # noqa: SLF001
        timeout=10,
    )


@pytest.fixture
def mocked_aws_server_envs(
    app_environment: EnvVarsDict,
    mocked_aws_server: ThreadedMotoServer,
    reset_aws_server_state: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs = {
        "EC2_CLUSTERS_KEEPER_ENDPOINT": f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access # noqa: SLF001
        "EC2_CLUSTERS_KEEPER_ACCESS_KEY_ID": "xxx",
        "EC2_CLUSTERS_KEEPER_SECRET_ACCESS_KEY": "xxx",
    }
    return app_environment | setenvs_from_dict(monkeypatch, changed_envs)


@pytest.fixture
def aws_allowed_ec2_instance_type_names_env(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs = {
        "PRIMARY_EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
            [
                "t2.xlarge",
                "t2.2xlarge",
                "g3.4xlarge",
                "r5n.4xlarge",
                "r5n.8xlarge",
            ]
        ),
    }
    return app_environment | setenvs_from_dict(monkeypatch, changed_envs)


@pytest.fixture
async def clusters_keeper_ec2(
    app_environment: EnvVarsDict,
) -> AsyncIterator[ClustersKeeperEC2]:
    settings = EC2ClustersKeeperSettings.create_from_envs()
    ec2 = await ClustersKeeperEC2.create(settings)
    assert ec2
    yield ec2
    await ec2.close()


@pytest.fixture
async def ec2_client(
    clusters_keeper_ec2: ClustersKeeperEC2,
) -> EC2Client:
    return clusters_keeper_ec2.client


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@pytest.fixture
def clusters_keeper_docker_compose() -> dict[str, Any]:
    data = importlib.resources.read_text(
        simcore_service_clusters_keeper.data, "docker-compose.yml"
    )
    assert data
    return yaml.safe_load(data)


@pytest.fixture
async def clusters_keeper_rabbitmq_rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]]
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("pytest_clusters_keeper_rpc_client")
    assert rpc_client
    return rpc_client


@pytest.fixture
def create_ec2_workers(
    aws_ami_id: str,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
    app_settings: ApplicationSettings,
) -> Callable[[int], Awaitable[list[str]]]:
    async def _do(num: int) -> list[str]:
        instance_type: InstanceTypeType = "c3.8xlarge"
        assert app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES
        instances = await ec2_client.run_instances(
            ImageId=aws_ami_id,
            MinCount=num,
            MaxCount=num,
            InstanceType=instance_type,
            KeyName=app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_KEY_NAME,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": f"{get_cluster_name(app_settings,user_id=user_id,wallet_id=wallet_id,is_manager=False)}_blahblah",
                        }
                    ],
                }
            ],
        )
        print(f"--> created {num} new instances of {instance_type=}")
        instance_ids = [
            i["InstanceId"] for i in instances["Instances"] if "InstanceId" in i
        ]
        waiter = ec2_client.get_waiter("instance_exists")
        await waiter.wait(InstanceIds=instance_ids)
        instances = await ec2_client.describe_instances(InstanceIds=instance_ids)
        assert "Reservations" in instances
        assert instances["Reservations"]
        assert "Instances" in instances["Reservations"][0]
        assert len(instances["Reservations"][0]["Instances"]) == num
        for instance in instances["Reservations"][0]["Instances"]:
            assert "State" in instance
            assert "Name" in instance["State"]
            assert instance["State"]["Name"] == "running"
            assert "Tags" in instance
            for tags in instance["Tags"]:
                assert "Key" in tags
                if "Name" in tags["Key"]:
                    assert "Value" in tags
                    assert (
                        get_cluster_name(
                            app_settings,
                            user_id=user_id,
                            wallet_id=wallet_id,
                            is_manager=False,
                        )
                        in tags["Value"]
                    )
        return instance_ids

    return _do
