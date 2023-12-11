# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import dataclasses
import datetime
import json
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, Final, cast
from unittest import mock

import aiodocker
import distributed
import httpx
import psutil
import pytest
import simcore_service_autoscaling
from asgi_lifespan import LifespanManager
from aws_library.ec2.models import EC2InstanceBootSpecific, EC2InstanceData
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
from pydantic import ByteSize, PositiveInt, parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_host import get_localhost_ip
from settings_library.rabbit import RabbitSettings
from simcore_service_autoscaling.core.application import create_app
from simcore_service_autoscaling.core.settings import (
    AUTOSCALING_ENV_PREFIX,
    ApplicationSettings,
    EC2Settings,
)
from simcore_service_autoscaling.models import Cluster, DaskTaskResources
from simcore_service_autoscaling.modules.docker import AutoscalingDocker
from tenacity import retry
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from types_aiobotocore_ec2.literals import InstanceTypeType

pytest_plugins = [
    "pytest_simcore.aws_server",
    "pytest_simcore.aws_ec2_service",
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
def mocked_ec2_server_envs(
    mocked_ec2_server_settings: EC2Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # NOTE: overrides the EC2Settings with what autoscaling expects
    changed_envs: EnvVarsDict = {
        f"{AUTOSCALING_ENV_PREFIX}{k}": v
        for k, v in mocked_ec2_server_settings.dict().items()
    }
    return setenvs_from_dict(monkeypatch, changed_envs)


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
            "AUTOSCALING_EC2_ACCESS": "{}",
            "AUTOSCALING_EC2_ACCESS_KEY_ID": faker.pystr(),
            "AUTOSCALING_EC2_SECRET_ACCESS_KEY": faker.pystr(),
            "AUTOSCALING_EC2_INSTANCES": "{}",
            "EC2_INSTANCES_KEY_NAME": faker.pystr(),
            "EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    ec2_type_name: random.choice(  # noqa: S311
                        EC2InstanceBootSpecific.Config.schema_extra["examples"]
                    )
                    for ec2_type_name in ec2_instances
                }
            ),
            "EC2_INSTANCES_CUSTOM_TAGS": json.dumps(
                {
                    "user_id": "32",
                    "wallet_id": "3245",
                    "osparc-tag": "some whatever value",
                }
            ),
        },
    )
    return mock_env_devel_environment | envs


@pytest.fixture
def mocked_ec2_instances_envs(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    aws_security_group_id: str,
    aws_subnet_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[InstanceTypeType],
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_KEY_NAME": "osparc-pytest",
            "EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps([aws_security_group_id]),
            "EC2_INSTANCES_SUBNET_ID": aws_subnet_id,
            "EC2_INSTANCES_AMI_ID": aws_ami_id,
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    ec2_type_name: random.choice(  # noqa: S311
                        EC2InstanceBootSpecific.Config.schema_extra["examples"]
                    )
                    | {"ami_id": aws_ami_id}
                    for ec2_type_name in aws_allowed_ec2_instance_type_names
                }
            ),
        },
    )
    return app_environment | envs


@pytest.fixture
def disable_dynamic_service_background_task(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_task.start_periodic_task",
        autospec=True,
    )

    mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_task.stop_periodic_task",
        autospec=True,
    )


@pytest.fixture
def enabled_dynamic_mode(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "AUTOSCALING_NODES_MONITORING": "{}",
            "NODES_MONITORING_NODE_LABELS": json.dumps(["pytest.fake-node-label"]),
            "NODES_MONITORING_SERVICE_LABELS": json.dumps(
                ["pytest.fake-service-label"]
            ),
            "NODES_MONITORING_NEW_NODES_LABELS": json.dumps(
                ["pytest.fake-new-node-label"]
            ),
        },
    )


@pytest.fixture
def enabled_computational_mode(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "AUTOSCALING_DASK": "{}",
            "DASK_MONITORING_URL": faker.url(),
            "DASK_MONITORING_USER_NAME": faker.user_name(),
            "DASK_MONITORING_PASSWORD": faker.password(),
        },
    )


@pytest.fixture
def disabled_rabbitmq(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTOSCALING_RABBITMQ", "null")


@pytest.fixture
def disabled_ec2(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOSCALING_EC2_ACCESS", "null")


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
        default_config = {
            "ID": faker.uuid4(),
            "Version": ObjectVersion(Index=faker.pyint()),
            "CreatedAt": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "UpdatedAt": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "Description": NodeDescription(
                Hostname=faker.pystr(),
                Resources=ResourceObject(
                    NanoCPUs=int(9 * 1e9), MemoryBytes=256 * 1024 * 1024 * 1024
                ),
            ),
            "Spec": NodeSpec(
                Name=None,
                Labels=None,
                Role=None,
                Availability=Availability.drain,
            ),
        }
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
        placement_constraints: list[str] | None = None,
    ) -> Service:
        service_name = f"pytest_{faker.pystr()}"
        base_labels = {}
        task_labels = task_template.setdefault("ContainerSpec", {}).setdefault(
            "Labels", base_labels
        )
        if placement_constraints:
            task_template.setdefault("Placement", {}).setdefault(
                "Constraints", placement_constraints
            )
        if labels:
            task_labels |= labels
            base_labels |= labels
        service = await async_docker_client.services.create(
            task_template=task_template,
            name=service_name,
            labels=base_labels,
        )
        assert service
        service = parse_obj_as(
            Service, await async_docker_client.services.inspect(service["ID"])
        )
        assert service.Spec
        print(f"--> created docker service {service.ID} with {service.Spec.Name}")
        assert service.Spec.Labels == base_labels

        created_services.append(service)
        # get more info on that service

        assert service.Spec.Name == service_name
        excluded_paths = {
            "ForceUpdate",
            "Runtime",
            "root['ContainerSpec']['Isolation']",
        }
        if not base_labels:
            excluded_paths.add("root['ContainerSpec']['Labels']")
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
        assert service.Spec.TaskTemplate
        diff = DeepDiff(
            task_template,
            service.Spec.TaskTemplate.dict(exclude_unset=True),
            exclude_paths=excluded_paths,
        )
        assert not diff, f"{diff}"
        assert service.Spec.Labels == base_labels
        await assert_for_service_state(
            async_docker_client, service, [wait_for_service_state]
        )
        return service

    yield _creator

    await asyncio.gather(
        *(async_docker_client.services.delete(s.ID) for s in created_services),
        return_exceptions=True,
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


@pytest.fixture(scope="session")
def aws_allowed_ec2_instance_type_names() -> list[InstanceTypeType]:
    return [
        "t2.xlarge",
        "t2.2xlarge",
        "g3.4xlarge",
        "g4dn.2xlarge",
        "g4dn.8xlarge",
        "r5n.4xlarge",
        "r5n.8xlarge",
    ]


@pytest.fixture
def aws_allowed_ec2_instance_type_names_env(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    aws_allowed_ec2_instance_type_names: list[InstanceTypeType],
) -> EnvVarsDict:
    changed_envs = {
        "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(aws_allowed_ec2_instance_type_names),
    }
    return app_environment | setenvs_from_dict(monkeypatch, changed_envs)


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
        {
            "user_id": faker.pyint(),
            "project_id": faker.uuid4(),
            "node_id": faker.uuid4(),
        }
    )


@pytest.fixture
def aws_instance_private_dns() -> str:
    return "ip-10-23-40-12.ec2.internal"


@pytest.fixture
def fake_localhost_ec2_instance_data(
    fake_ec2_instance_data: Callable[..., EC2InstanceData]
) -> EC2InstanceData:
    local_ip = get_localhost_ip()
    fake_local_ec2_private_dns = f"ip-{local_ip.replace('.', '-')}.ec2.internal"
    return fake_ec2_instance_data(aws_private_dns=fake_local_ec2_private_dns)


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)


@pytest.fixture
def cluster() -> Callable[..., Cluster]:
    def _creator(**cluter_overrides) -> Cluster:
        return dataclasses.replace(
            Cluster(
                active_nodes=[],
                drained_nodes=[],
                reserve_drained_nodes=[],
                pending_ec2s=[],
                disconnected_nodes=[],
                terminated_instances=[],
            ),
            **cluter_overrides,
        )

    return _creator


@pytest.fixture
async def create_dask_task(
    dask_spec_cluster_client: distributed.Client,
) -> Callable[[DaskTaskResources], distributed.Future]:
    def _remote_pytest_fct(x: int, y: int) -> int:
        return x + y

    def _creator(required_resources: DaskTaskResources) -> distributed.Future:
        # NOTE: pure will ensure dask does not re-use the task results if we run it several times
        future = dask_spec_cluster_client.submit(
            _remote_pytest_fct, 23, 43, resources=required_resources, pure=False
        )
        assert future
        return future

    return _creator


@pytest.fixture
def mock_docker_set_node_availability(mocker: MockerFixture) -> mock.Mock:
    async def _fake_set_node_availability(
        docker_client: AutoscalingDocker, node: Node, *, available: bool
    ) -> Node:
        returned_node = deepcopy(node)
        assert returned_node.Spec
        returned_node.Spec.Availability = (
            Availability.active if available else Availability.drain
        )
        returned_node.UpdatedAt = datetime.datetime.now(
            tz=datetime.timezone.utc
        ).isoformat()
        return returned_node

    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.set_node_availability",
        autospec=True,
        side_effect=_fake_set_node_availability,
    )
