# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import random
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import timezone
from pathlib import Path

import aiodocker
import httpx
import pytest
import requests
import simcore_service_clusters_keeper
from aiohttp.test_utils import unused_port
from asgi_lifespan import LifespanManager
from faker import Faker
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from moto.server import ThreadedMotoServer
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from settings_library.rabbit import RabbitSettings
from simcore_service_clusters_keeper.core.application import create_app
from simcore_service_clusters_keeper.core.settings import (
    ApplicationSettings,
    EC2Settings,
)
from simcore_service_clusters_keeper.modules.ec2 import (
    ClustersKeeperEC2,
    EC2InstanceData,
)
from types_aiobotocore_ec2.client import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType

pytest_plugins = [
    "pytest_simcore.dask_gateway",
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
            "EC2_ACCESS_KEY_ID": faker.pystr(),
            "EC2_SECRET_ACCESS_KEY": faker.pystr(),
            "EC2_INSTANCES_KEY_NAME": faker.pystr(),
            "EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "EC2_INSTANCES_AMI_ID": faker.pystr(),
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(ec2_instances),
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
    monkeypatch.delenv("EC2_ACCESS_KEY_ID")


@pytest.fixture
def enabled_rabbitmq(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitSettings:
    return rabbit_service


@pytest.fixture
async def initialized_app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app):
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
        "EC2_ENDPOINT": f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access # noqa: SLF001
        "EC2_ACCESS_KEY_ID": "xxx",
        "EC2_SECRET_ACCESS_KEY": "xxx",
    }
    return app_environment | setenvs_from_dict(monkeypatch, changed_envs)


@pytest.fixture
def aws_allowed_ec2_instance_type_names(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs = {
        "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
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


@pytest.fixture(scope="session")
def vpc_cidr_block() -> str:
    return "10.0.0.0/16"


@pytest.fixture
async def aws_vpc_id(
    mocked_aws_server_envs: None,
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    ec2_client: EC2Client,
    vpc_cidr_block: str,
) -> AsyncIterator[str]:
    vpc = await ec2_client.create_vpc(
        CidrBlock=vpc_cidr_block,
    )
    vpc_id = vpc["Vpc"]["VpcId"]  # type: ignore
    print(f"--> Created Vpc in AWS with {vpc_id=}")
    yield vpc_id

    await ec2_client.delete_vpc(VpcId=vpc_id)
    print(f"<-- Deleted Vpc in AWS with {vpc_id=}")


@pytest.fixture(scope="session")
def subnet_cidr_block() -> str:
    return "10.0.1.0/24"


@pytest.fixture
async def aws_subnet_id(
    monkeypatch: pytest.MonkeyPatch,
    aws_vpc_id: str,
    ec2_client: EC2Client,
    subnet_cidr_block: str,
) -> AsyncIterator[str]:
    subnet = await ec2_client.create_subnet(
        CidrBlock=subnet_cidr_block, VpcId=aws_vpc_id
    )
    assert "Subnet" in subnet
    assert "SubnetId" in subnet["Subnet"]
    subnet_id = subnet["Subnet"]["SubnetId"]
    print(f"--> Created Subnet in AWS with {subnet_id=}")

    monkeypatch.setenv("EC2_INSTANCES_SUBNET_ID", subnet_id)
    yield subnet_id

    # all the instances in the subnet must be terminated before that works
    instances_in_subnet = await ec2_client.describe_instances(
        Filters=[{"Name": "subnet-id", "Values": [subnet_id]}]
    )
    if instances_in_subnet["Reservations"]:
        print(f"--> terminating {len(instances_in_subnet)} instances in subnet")
        await ec2_client.terminate_instances(
            InstanceIds=[
                instance["Instances"][0]["InstanceId"]  # type: ignore
                for instance in instances_in_subnet["Reservations"]
            ]
        )
        print(f"<-- terminated {len(instances_in_subnet)} instances in subnet")

    await ec2_client.delete_subnet(SubnetId=subnet_id)
    subnets = await ec2_client.describe_subnets()
    print(f"<-- Deleted Subnet in AWS with {subnet_id=}")
    print(f"current {subnets=}")


@pytest.fixture
async def aws_security_group_id(
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    aws_vpc_id: str,
    ec2_client: EC2Client,
) -> AsyncIterator[str]:
    security_group = await ec2_client.create_security_group(
        Description=faker.text(), GroupName=faker.pystr(), VpcId=aws_vpc_id
    )
    security_group_id = security_group["GroupId"]
    print(f"--> Created Security Group in AWS with {security_group_id=}")
    monkeypatch.setenv(
        "EC2_INSTANCES_SECURITY_GROUP_IDS", json.dumps([security_group_id])
    )
    yield security_group_id
    await ec2_client.delete_security_group(GroupId=security_group_id)
    print(f"<-- Deleted Security Group in AWS with {security_group_id=}")


@pytest.fixture
async def aws_ami_id(
    app_environment: EnvVarsDict,
    mocked_aws_server_envs: None,
    monkeypatch: pytest.MonkeyPatch,
    ec2_client: EC2Client,
) -> str:
    images = await ec2_client.describe_images()
    image = random.choice(images["Images"])  # noqa S311
    ami_id = image["ImageId"]  # type: ignore
    monkeypatch.setenv("EC2_INSTANCES_AMI_ID", ami_id)
    return ami_id


@pytest.fixture
async def clusters_keeper_ec2(
    app_environment: EnvVarsDict,
) -> AsyncIterator[ClustersKeeperEC2]:
    settings = EC2Settings.create_from_envs()
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
def fake_ec2_instance_data(faker: Faker) -> Callable[..., EC2InstanceData]:
    def _creator(**overrides) -> EC2InstanceData:
        return EC2InstanceData(
            **(
                {
                    "launch_time": faker.date_time(tzinfo=timezone.utc),
                    "id": faker.uuid4(),
                    "aws_private_dns": faker.name(),
                    "aws_public_ip": faker.ipv4_public(),
                    "type": faker.pystr(),
                    "state": faker.pystr(),
                    "tags": faker.pydict(allowed_types=(str,)),
                }
                | overrides
            )
        )

    return _creator


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client
