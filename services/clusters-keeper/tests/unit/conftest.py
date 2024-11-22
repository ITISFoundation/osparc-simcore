# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import importlib.resources
import json
import random
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import aiodocker
import httpx
import pytest
import simcore_service_clusters_keeper
import simcore_service_clusters_keeper.data
import yaml
from asgi_lifespan import LifespanManager
from aws_library.ec2 import EC2InstanceBootSpecific
from faker import Faker
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import SecretStr
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.ec2 import EC2Settings
from settings_library.rabbit import RabbitSettings
from settings_library.ssm import SSMSettings
from simcore_service_clusters_keeper.core.application import create_app
from simcore_service_clusters_keeper.core.settings import (
    CLUSTERS_KEEPER_ENV_PREFIX,
    ApplicationSettings,
)
from simcore_service_clusters_keeper.utils.ec2 import get_cluster_name
from types_aiobotocore_ec2.client import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType

pytest_plugins = [
    "pytest_simcore.aws_ec2_service",
    "pytest_simcore.aws_server",
    "pytest_simcore.docker",
    "pytest_simcore.dask_scheduler",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_service_library_fixtures",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "clusters-keeper"
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
def mocked_ec2_server_envs(
    mocked_ec2_server_settings: EC2Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # NOTE: overrides the EC2Settings with what clusters-keeper expects
    changed_envs: EnvVarsDict = {
        f"{CLUSTERS_KEEPER_ENV_PREFIX}{k}": v
        for k, v in mocked_ec2_server_settings.model_dump().items()
    }
    return setenvs_from_dict(monkeypatch, changed_envs)


@pytest.fixture
def mocked_ssm_server_envs(
    mocked_ssm_server_settings: SSMSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # NOTE: overrides the SSMSettings with what clusters-keeper expects
    changed_envs: EnvVarsDict = {
        f"{CLUSTERS_KEEPER_ENV_PREFIX}{k}": (
            v.get_secret_value() if isinstance(v, SecretStr) else v
        )
        for k, v in mocked_ssm_server_settings.model_dump().items()
    }
    return setenvs_from_dict(monkeypatch, changed_envs)


@pytest.fixture
def ec2_settings(mocked_ec2_server_settings: EC2Settings) -> EC2Settings:
    return mocked_ec2_server_settings


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
            "CLUSTERS_KEEPER_TRACING": "null",
            "CLUSTERS_KEEPER_EC2_ACCESS": "{}",
            "CLUSTERS_KEEPER_EC2_ACCESS_KEY_ID": faker.pystr(),
            "CLUSTERS_KEEPER_EC2_SECRET_ACCESS_KEY": faker.pystr(),
            "CLUSTERS_KEEPER_SSM_ACCESS": "{}",
            "CLUSTERS_KEEPER_SSM_ACCESS_KEY_ID": faker.pystr(),
            "CLUSTERS_KEEPER_SSM_SECRET_ACCESS_KEY": faker.pystr(),
            "CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES": "{}",
            "CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX": faker.pystr(),
            "CLUSTERS_KEEPER_DASK_NTHREADS": f"{faker.pyint(min_value=0)}",
            "CLUSTERS_KEEPER_DASK_WORKER_SATURATION": f"{faker.pyfloat(min_value=0.1)}",
            "CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH": "{}",
            "PRIMARY_EC2_INSTANCES_KEY_NAME": faker.pystr(),
            "PRIMARY_EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "PRIMARY_EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "PRIMARY_EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    random.choice(  # noqa: S311
                        ec2_instances
                    ): EC2InstanceBootSpecific.model_config["json_schema_extra"][
                        "examples"
                    ][
                        1
                    ]  # NOTE: we use example with custom script
                }
            ),
            "PRIMARY_EC2_INSTANCES_CUSTOM_TAGS": json.dumps(
                {"osparc-tag": "the pytest tag is here"}
            ),
            "PRIMARY_EC2_INSTANCES_ATTACHED_IAM_PROFILE": "",  # must be empty since we would need to add it to moto as well
            "PRIMARY_EC2_INSTANCES_SSM_TLS_DASK_CA": faker.pystr(),
            "PRIMARY_EC2_INSTANCES_SSM_TLS_DASK_CERT": faker.pystr(),
            "PRIMARY_EC2_INSTANCES_SSM_TLS_DASK_KEY": faker.pystr(),
            "PRIMARY_EC2_INSTANCES_PROMETHEUS_USERNAME": faker.user_name(),
            "PRIMARY_EC2_INSTANCES_PROMETHEUS_PASSWORD": faker.password(),
            "CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES": "{}",
            "WORKERS_EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    ec2_type_name: random.choice(  # noqa: S311
                        EC2InstanceBootSpecific.model_config["json_schema_extra"][
                            "examples"
                        ]
                    )
                    for ec2_type_name in ec2_instances
                }
            ),
            "WORKERS_EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "WORKERS_EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "WORKERS_EC2_INSTANCES_KEY_NAME": faker.pystr(),
            "WORKERS_EC2_INSTANCES_CUSTOM_TAGS": json.dumps(
                {"osparc-tag": "the pytest worker tag value is here"}
            ),
        },
    )
    return mock_env_devel_environment | envs


@pytest.fixture
def mocked_primary_ec2_instances_envs(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    aws_security_group_id: str,
    aws_subnet_id: str,
    aws_ami_id: str,
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "PRIMARY_EC2_INSTANCES_KEY_NAME": "osparc-pytest",
            "PRIMARY_EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                [aws_security_group_id]
            ),
            "PRIMARY_EC2_INSTANCES_SUBNET_ID": aws_subnet_id,
        },
    )
    return app_environment | envs


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
    monkeypatch.setenv("CLUSTERS_KEEPER_RABBITMQ", "null")


@pytest.fixture
def disabled_ec2(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLUSTERS_KEEPER_EC2_ACCESS", "null")


@pytest.fixture
def disabled_ssm(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLUSTERS_KEEPER_SSM_ACCESS", "null")


@pytest.fixture
def enabled_rabbitmq(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitSettings:
    return rabbit_service


@pytest.fixture
async def initialized_app(
    app_environment: EnvVarsDict, is_pdb_enabled: bool
) -> AsyncIterator[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app, shutdown_timeout=None if is_pdb_enabled else 20):
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


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@pytest.fixture
def clusters_keeper_docker_compose_file(installed_package_dir: Path) -> Path:
    docker_compose_path = installed_package_dir / "data" / "docker-compose.yml"
    assert docker_compose_path.exists()
    return docker_compose_path


@pytest.fixture
def clusters_keeper_docker_compose() -> dict[str, Any]:
    data = (
        importlib.resources.files(simcore_service_clusters_keeper.data)
        .joinpath("docker-compose.yml")
        .read_text()
    )
    assert data
    return yaml.safe_load(data)


@pytest.fixture
async def clusters_keeper_rabbitmq_rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
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
