# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json
import random
from datetime import timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Final, Iterator, cast

import aiodocker
import httpx
import psutil
import pytest
import requests
import simcore_service_autoscaling
from aiohttp.test_utils import unused_port
from asgi_lifespan import LifespanManager
from deepdiff import DeepDiff
from faker import Faker
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from models_library.docker import DockerLabelKey, StandardSimcoreDockerLabels
from models_library.generated_models.docker_rest_api import (
    Availability,
    Node,
    NodeDescription,
    NodeSpec,
    ObjectVersion,
    ResourceObject,
    Service,
)
from moto.server import ThreadedMotoServer
from pydantic import ByteSize, PositiveInt, parse_obj_as
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from settings_library.rabbit import RabbitSettings
from simcore_service_autoscaling.core.application import create_app
from simcore_service_autoscaling.core.settings import ApplicationSettings, EC2Settings
from simcore_service_autoscaling.modules.docker import AutoscalingDocker
from simcore_service_autoscaling.modules.ec2 import AutoscalingEC2, EC2InstanceData
from tenacity import retry
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from types_aiobotocore_ec2.client import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "autoscaling"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_autoscaling"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_autoscaling.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def ec2_instances() -> list[InstanceTypeType]:
    # these are some examples
    return ["t2.nano", "m5.12xlarge"]


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: MonkeyPatch,
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
            "NODES_MONITORING_NODE_LABELS": json.dumps(["pytest.fake-node-label"]),
            "NODES_MONITORING_SERVICE_LABELS": json.dumps(
                ["pytest.fake-service-label"]
            ),
            "NODES_MONITORING_NEW_NODES_LABELS": json.dumps(
                ["pytest.fake-new-node-label"]
            ),
        },
    )
    return mock_env_devel_environment | envs


@pytest.fixture
def disable_dynamic_service_background_task(mocker: MockerFixture) -> Iterator[None]:
    mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling.start_periodic_task",
        autospec=True,
    )

    mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling.stop_periodic_task",
        autospec=True,
    )

    yield


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
def service_monitored_labels(
    app_settings: ApplicationSettings,
) -> dict[DockerLabelKey, str]:
    assert app_settings.AUTOSCALING_NODES_MONITORING
    return {
        key: "true"
        for key in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS
    }


@pytest.fixture
async def async_client(initialized_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url=f"http://{initialized_app.title}.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
async def autoscaling_docker() -> AsyncIterator[AutoscalingDocker]:
    async with AutoscalingDocker() as docker_client:
        yield cast(AutoscalingDocker, docker_client)


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@pytest.fixture
async def host_node(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
) -> Node:
    nodes = parse_obj_as(list[Node], await async_docker_client.nodes.list())
    assert len(nodes) == 1
    return nodes[0]


@pytest.fixture
def create_fake_node(faker: Faker) -> Callable[..., Node]:
    def _creator(**node_overrides) -> Node:
        default_config = dict(
            ID=faker.uuid4(),
            Version=ObjectVersion(Index=faker.pyint()),
            CreatedAt=faker.date_time(tzinfo=timezone.utc).isoformat(),
            UpdatedAt=faker.date_time(tzinfo=timezone.utc).isoformat(),
            Description=NodeDescription(
                Hostname=faker.pystr(),
                Resources=ResourceObject(
                    NanoCPUs=int(9 * 1e9), MemoryBytes=256 * 1024 * 1024 * 1024
                ),
            ),
            Spec=NodeSpec(
                Name=None,
                Labels=None,
                Role=None,
                Availability=Availability.drain,
            ),
        )
        default_config.update(**node_overrides)
        return Node(**default_config)

    return _creator


@pytest.fixture
def fake_node(create_fake_node: Callable[..., Node]) -> Node:
    return create_fake_node()


@pytest.fixture
def task_template() -> dict[str, Any]:
    return {
        "ContainerSpec": {
            "Image": "redis:7.0.5-alpine",
        },
    }


_GIGA_NANO_CPU = 10**9
NUM_CPUS = PositiveInt


@pytest.fixture
def create_task_reservations() -> Callable[[NUM_CPUS, int], dict[str, Any]]:
    def _creator(num_cpus: NUM_CPUS, memory: ByteSize | int) -> dict[str, Any]:
        return {
            "Resources": {
                "Reservations": {
                    "NanoCPUs": num_cpus * _GIGA_NANO_CPU,
                    "MemoryBytes": int(memory),
                }
            }
        }

    return _creator


@pytest.fixture
def create_task_limits() -> Callable[[NUM_CPUS, int], dict[str, Any]]:
    def _creator(num_cpus: NUM_CPUS, memory: ByteSize | int) -> dict[str, Any]:
        return {
            "Resources": {
                "Limits": {
                    "NanoCPUs": num_cpus * _GIGA_NANO_CPU,
                    "MemoryBytes": int(memory),
                }
            }
        }

    return _creator


@pytest.fixture
async def create_service(
    async_docker_client: aiodocker.Docker,
    docker_swarm: None,
    faker: Faker,
) -> AsyncIterator[
    Callable[[dict[str, Any], dict[DockerLabelKey, str] | None], Awaitable[Service]]
]:
    created_services = []

    async def _creator(
        task_template: dict[str, Any],
        labels: dict[DockerLabelKey, str] | None = None,
        wait_for_service_state="running",
    ) -> Service:
        service_name = f"pytest_{faker.pystr()}"
        if labels:
            task_labels = task_template.setdefault("ContainerSpec", {}).setdefault(
                "Labels", {}
            )
            task_labels |= labels
        service = await async_docker_client.services.create(
            task_template=task_template,
            name=service_name,
            labels=labels or {},  # type: ignore
        )
        assert service
        service = parse_obj_as(
            Service, await async_docker_client.services.inspect(service["ID"])
        )
        assert service.Spec
        print(f"--> created docker service {service.ID} with {service.Spec.Name}")
        assert service.Spec.Labels == (labels or {})

        created_services.append(service)
        # get more info on that service

        assert service.Spec.Name == service_name
        excluded_paths = {
            "ForceUpdate",
            "Runtime",
            "root['ContainerSpec']['Isolation']",
        }
        for reservation in ["MemoryBytes", "NanoCPUs"]:
            if (
                task_template.get("Resources", {})
                .get("Reservations", {})
                .get(reservation, 0)
                == 0
            ):
                # NOTE: if a 0 memory reservation is done, docker removes it from the task inspection
                excluded_paths.add(
                    f"root['Resources']['Reservations']['{reservation}']"
                )
        diff = DeepDiff(
            task_template,
            service.Spec.TaskTemplate.dict(exclude_unset=True),
            exclude_paths=excluded_paths,
        )
        assert not diff, f"{diff}"
        assert service.Spec.Labels == (labels or {})
        await assert_for_service_state(
            async_docker_client, service, [wait_for_service_state]
        )
        return service

    yield _creator

    await asyncio.gather(
        *(async_docker_client.services.delete(s.ID) for s in created_services)
    )

    # wait until all tasks are gone
    @retry(
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    )
    async def _check_service_task_gone(service: Service) -> None:
        assert service.Spec
        print(
            f"--> checking if service {service.ID}:{service.Spec.Name} is really gone..."
        )
        assert not await async_docker_client.containers.list(
            all=True,
            filters={
                "label": [f"com.docker.swarm.service.id={service.ID}"],
            },
        )
        print(f"<-- service {service.ID}:{service.Spec.Name} is gone.")

    await asyncio.gather(*(_check_service_task_gone(s) for s in created_services))
    await asyncio.sleep(0)


async def assert_for_service_state(
    async_docker_client: aiodocker.Docker, service: Service, expected_states: list[str]
) -> None:
    SUCCESS_STABLE_TIME_S: Final[float] = 3
    WAIT_TIME: Final[float] = 0.5
    number_of_success = 0
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
        wait=wait_fixed(WAIT_TIME),
        stop=stop_after_delay(10 * SUCCESS_STABLE_TIME_S),
    ):
        with attempt:
            print(
                f"--> waiting for service {service.ID} to become {expected_states}..."
            )
            services = await async_docker_client.services.list(
                filters={"id": service.ID}
            )
            assert services, f"no service with {service.ID}!"
            assert len(services) == 1
            found_service = services[0]

            tasks = await async_docker_client.tasks.list(
                filters={"service": found_service["Spec"]["Name"]}
            )
            assert tasks, f"no tasks available for {found_service['Spec']['Name']}"
            assert len(tasks) == 1
            service_task = tasks[0]
            assert (
                service_task["Status"]["State"] in expected_states
            ), f"service {found_service['Spec']['Name']}'s task is {service_task['Status']['State']}"
            print(
                f"<-- service {found_service['Spec']['Name']} is now {service_task['Status']['State']} {'.'*number_of_success}"
            )
            number_of_success += 1
            assert (number_of_success * WAIT_TIME) >= SUCCESS_STABLE_TIME_S
            print(
                f"<-- service {found_service['Spec']['Name']} is now {service_task['Status']['State']} after {SUCCESS_STABLE_TIME_S} seconds"
            )


@pytest.fixture(scope="module")
def mocked_aws_server() -> Iterator[ThreadedMotoServer]:
    """creates a moto-server that emulates AWS services in place
    NOTE: Never use a bucket with underscores it fails!!
    """
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=unused_port())
    # pylint: disable=protected-access
    print(f"--> started mock AWS server on {server._ip_address}:{server._port}")
    print(
        f"--> Dashboard available on [http://{server._ip_address}:{server._port}/moto-api/]"
    )
    server.start()
    yield server
    server.stop()
    print(f"<-- stopped mock AWS server on {server._ip_address}:{server._port}")


@pytest.fixture
def reset_aws_server_state(mocked_aws_server: ThreadedMotoServer) -> Iterator[None]:
    # NOTE: reset_aws_server_state [http://docs.getmoto.org/en/latest/docs/server_mode.html#reset-api]
    yield
    # pylint: disable=protected-access
    requests.post(
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}/moto-api/reset",
        timeout=10,
    )


@pytest.fixture
def mocked_aws_server_envs(
    app_environment: EnvVarsDict,
    mocked_aws_server: ThreadedMotoServer,
    reset_aws_server_state: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[EnvVarsDict]:
    changed_envs = {
        "EC2_ENDPOINT": f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access
        "EC2_ACCESS_KEY_ID": "xxx",
        "EC2_SECRET_ACCESS_KEY": "xxx",
    }
    yield app_environment | setenvs_from_dict(monkeypatch, changed_envs)


@pytest.fixture
def aws_allowed_ec2_instance_type_names(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[EnvVarsDict]:
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
    yield app_environment | setenvs_from_dict(monkeypatch, changed_envs)


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
    image = random.choice(images["Images"])
    ami_id = image["ImageId"]  # type: ignore
    monkeypatch.setenv("EC2_INSTANCES_AMI_ID", ami_id)
    return ami_id


@pytest.fixture
async def autoscaling_ec2(
    app_environment: EnvVarsDict,
) -> AsyncIterator[AutoscalingEC2]:
    settings = EC2Settings.create_from_envs()
    ec2 = await AutoscalingEC2.create(settings)
    assert ec2
    yield ec2
    await ec2.close()


@pytest.fixture
async def ec2_client(
    autoscaling_ec2: AutoscalingEC2,
) -> AsyncIterator[EC2Client]:
    yield autoscaling_ec2.client


@pytest.fixture
def host_cpu_count() -> int:
    return psutil.cpu_count()


@pytest.fixture
def host_memory_total() -> ByteSize:
    return ByteSize(psutil.virtual_memory().total)


@pytest.fixture
def osparc_docker_label_keys(
    faker: Faker,
) -> StandardSimcoreDockerLabels:
    return StandardSimcoreDockerLabels.parse_obj(
        dict(user_id=faker.pyint(), project_id=faker.uuid4(), node_id=faker.uuid4())
    )


@pytest.fixture
def aws_instance_private_dns() -> str:
    return "ip-10-23-40-12.ec2.internal"


@pytest.fixture
def fake_ec2_instance_data(faker: Faker) -> Callable[..., EC2InstanceData]:
    def _creator(**overrides) -> EC2InstanceData:
        return EC2InstanceData(
            **(
                {
                    "launch_time": faker.date_time(tzinfo=timezone.utc),
                    "id": faker.uuid4(),
                    "aws_private_dns": faker.name(),
                    "type": faker.pystr(),
                    "state": faker.pystr(),
                }
                | overrides
            )
        )

    return _creator


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)
