# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json
import random
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Final,
    Iterator,
    Mapping,
    Optional,
    Union,
)

import aiodocker
import httpx
import psutil
import pytest
import simcore_service_autoscaling
from aiohttp.test_utils import unused_port
from asgi_lifespan import LifespanManager
from deepdiff import DeepDiff
from faker import Faker
from fastapi import FastAPI
from moto.server import ThreadedMotoServer
from pydantic import ByteSize, PositiveInt
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.core.application import create_app
from simcore_service_autoscaling.core.settings import ApplicationSettings, AwsSettings
from simcore_service_autoscaling.utils_aws import EC2Client
from simcore_service_autoscaling.utils_aws import ec2_client as autoscaling_ec2_client
from tenacity import retry
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_plugins = [
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
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


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict, monkeypatch: MonkeyPatch, faker: Faker
) -> EnvVarsDict:
    # SEE https://faker.readthedocs.io/en/master/providers/faker.providers.internet.html?highlight=internet#faker-providers-internet
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "AWS_KEY_NAME": "TODO",
            "AWS_DNS": faker.domain_name(),
            "AWS_ACCESS_KEY_ID": "str",
            "AWS_SECRET_ACCESS_KEY": "str",
            "AWS_SECURITY_GROUP_IDS": '["a", "b"]',
            "AWS_SUBNET_ID": "str",
            # "AWS_ENDPOINT": "null",
        },
    )
    return mock_env_devel_environment | envs


@pytest.fixture(scope="function")
async def initialized_app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def app_settings(initialized_app: FastAPI) -> ApplicationSettings:
    assert initialized_app.state.settings
    return initialized_app.state.settings


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:

    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://director-v2.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@pytest.fixture
def task_template() -> dict[str, Any]:
    return {
        "ContainerSpec": {
            "Image": "redis",
        },
    }


_GIGA_NANO_CPU = 10**9
NUM_CPUS = PositiveInt


@pytest.fixture
def create_task_resources() -> Callable[[NUM_CPUS, int], dict[str, Any]]:
    def _creator(num_cpus: NUM_CPUS, memory: Union[ByteSize, int]) -> dict[str, Any]:
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
async def create_service(
    async_docker_client: aiodocker.Docker,
    docker_swarm: None,
    faker: Faker,
) -> AsyncIterator[
    Callable[[dict[str, Any], Optional[dict[str, str]]], Awaitable[Mapping[str, Any]]]
]:
    created_services = []

    async def _creator(
        task_template: dict[str, Any], labels: Optional[dict[str, str]] = None
    ) -> Mapping[str, Any]:
        service_name = f"pytest_{faker.pystr()}"
        service = await async_docker_client.services.create(
            task_template=task_template,
            name=service_name,
            labels=labels or {},  # type: ignore
        )
        assert service
        service = await async_docker_client.services.inspect(service["ID"])
        print(
            f"--> created docker service {service['ID']} with {service['Spec']['Name']}"
        )

        created_services.append(service)
        # get more info on that service

        assert service["Spec"]["Name"] == service_name
        excluded_paths = {
            "ForceUpdate",
            "Runtime",
            "root['ContainerSpec']['Isolation']",
        }
        if (
            task_template.get("Resources", {})
            .get("Reservations", {})
            .get("MemoryBytes", 0)
            == 0
        ):
            # NOTE: if a 0 memory reservation is done, docker removes it from the task inspection
            excluded_paths.add("root['Resources']['Reservations']['MemoryBytes']")
        diff = DeepDiff(
            task_template,
            service["Spec"]["TaskTemplate"],
            exclude_paths=excluded_paths,
        )
        assert not diff, f"{diff}"
        assert service["Spec"]["Labels"] == (labels or {})

        return service

    yield _creator
    await asyncio.gather(
        *(async_docker_client.services.delete(s["ID"]) for s in created_services)
    )
    # wait until all tasks are gone
    @retry(
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
        wait=wait_fixed(0.5),
        stop=stop_after_delay(10),
    )
    async def _check_service_task_gone(service: Mapping[str, Any]) -> None:
        print(
            f"--> checking if service {service['ID']}:{service['Spec']['Name']} is really gone..."
        )
        assert not await async_docker_client.containers.list(
            filters={
                "is-task": ["true"],
                "label": [f"com.docker.swarm.service.id={service['ID']}"],
            }
        )
        print(
            f"<-- checking if service {service['ID']}:{service['Spec']['Name']} is gone."
        )

    await asyncio.gather(*(_check_service_task_gone(s) for s in created_services))


@pytest.fixture
def assert_for_service_state() -> Callable[
    [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
]:
    async def _runner(
        async_docker_client: aiodocker.Docker,
        created_service: Mapping[str, Any],
        expected_states: list[str],
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
                    f"--> waiting for service {created_service['ID']} to become {expected_states}..."
                )
                services = await async_docker_client.services.list(
                    filters={"id": created_service["ID"]}
                )
                assert services, f"no service with {created_service['ID']}!"
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

    return _runner


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
def mocked_aws_server_envs(
    mocked_aws_server: ThreadedMotoServer, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setenv(
        "AWS_ENDPOINT",
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access
    )
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "xxx")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "xxx")

    yield


@pytest.fixture
def ec2_client() -> Iterator[EC2Client]:
    settings = AwsSettings.create_from_envs()
    with autoscaling_ec2_client(settings) as client:
        yield client


@pytest.fixture
def aws_vpc_id(
    mocked_aws_server_envs: None,
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    ec2_client: EC2Client,
) -> Iterator[str]:
    vpc = ec2_client.create_vpc(
        CidrBlock="10.0.0.0/16",
    )
    vpc_id = vpc["Vpc"]["VpcId"]  # type: ignore
    print(f"--> Created Vpc in AWS with {vpc_id=}")
    monkeypatch.setenv("AWS_VPC_ID", vpc_id)
    yield vpc_id

    ec2_client.delete_vpc(VpcId=vpc_id)
    print(f"<-- Deleted Vpc in AWS with {vpc_id=}")


@pytest.fixture
def aws_subnet_id(
    monkeypatch: pytest.MonkeyPatch,
    aws_vpc_id: str,
    ec2_client: EC2Client,
) -> Iterator[str]:
    subnet = ec2_client.create_subnet(CidrBlock="10.0.1.0/24", VpcId=aws_vpc_id)
    assert "Subnet" in subnet
    assert "SubnetId" in subnet["Subnet"]
    subnet_id = subnet["Subnet"]["SubnetId"]
    print(f"--> Created Subnet in AWS with {subnet_id=}")

    monkeypatch.setenv("AWS_SUBNET_ID", subnet_id)
    yield subnet_id
    ec2_client.delete_subnet(SubnetId=subnet_id)
    print(f"<-- Deleted Subnet in AWS with {subnet_id=}")


@pytest.fixture
def aws_security_group_id(
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    aws_vpc_id: str,
    ec2_client: EC2Client,
) -> Iterator[str]:
    security_group = ec2_client.create_security_group(
        Description=faker.text(), GroupName=faker.pystr(), VpcId=aws_vpc_id
    )
    security_group_id = security_group["GroupId"]
    print(f"--> Created Security Group in AWS with {security_group_id=}")
    monkeypatch.setenv("AWS_SECURITY_GROUP_IDS", json.dumps([security_group_id]))
    yield security_group_id
    ec2_client.delete_security_group(GroupId=security_group_id)
    print(f"<-- Deleted Security Group in AWS with {security_group_id=}")


@pytest.fixture
def aws_ami_id(
    mocked_aws_server_envs: None,
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    ec2_client: EC2Client,
) -> str:
    images = ec2_client.describe_images()
    image = random.choice(images["Images"])
    ami_id = image["ImageId"]  # type: ignore
    monkeypatch.setenv("AWS_AMI_ID", ami_id)
    return ami_id


@pytest.fixture
def host_cpu_count() -> int:
    return psutil.cpu_count()


@pytest.fixture
def host_memory_total() -> ByteSize:
    return ByteSize(psutil.virtual_memory().total)
