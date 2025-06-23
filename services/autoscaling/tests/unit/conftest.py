# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import dataclasses
import datetime
import json
import logging
import random
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any, Final, TypeAlias, cast, get_args
from unittest import mock

import aiodocker
import arrow
import distributed
import httpx
import psutil
import pytest
import simcore_service_autoscaling
from asgi_lifespan import LifespanManager
from aws_library.ec2 import (
    EC2InstanceBootSpecific,
    EC2InstanceData,
    EC2InstanceType,
    Resources,
)
from common_library.json_serialization import json_dumps
from deepdiff import DeepDiff
from faker import Faker
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from models_library.docker import (
    DockerGenericTag,
    DockerLabelKey,
    StandardSimcoreDockerLabels,
)
from models_library.generated_models.docker_rest_api import (
    Availability,
)
from models_library.generated_models.docker_rest_api import Node as DockerNode
from models_library.generated_models.docker_rest_api import (
    NodeDescription,
    NodeSpec,
    NodeState,
    NodeStatus,
    ObjectVersion,
    ResourceObject,
    Service,
    TaskSpec,
)
from pydantic import ByteSize, NonNegativeInt, PositiveInt, TypeAdapter
from pytest_mock import MockType
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
    delenvs_from_dict,
    setenvs_from_dict,
)
from settings_library.rabbit import RabbitSettings
from settings_library.ssm import SSMSettings
from simcore_service_autoscaling.constants import PRE_PULLED_IMAGES_EC2_TAG_KEY
from simcore_service_autoscaling.core.application import create_app
from simcore_service_autoscaling.core.settings import (
    AUTOSCALING_ENV_PREFIX,
    ApplicationSettings,
    AutoscalingEC2Settings,
    EC2InstancesSettings,
    EC2Settings,
)
from simcore_service_autoscaling.models import (
    AssociatedInstance,
    Cluster,
    DaskTaskResources,
)
from simcore_service_autoscaling.modules.cluster_scaling import _auto_scaling_core
from simcore_service_autoscaling.modules.cluster_scaling._provider_dynamic import (
    DynamicAutoscalingProvider,
)
from simcore_service_autoscaling.modules.docker import AutoscalingDocker
from simcore_service_autoscaling.modules.ec2 import SimcoreEC2API
from simcore_service_autoscaling.utils.buffer_machines_pool_core import (
    get_deactivated_buffer_ec2_tags,
)
from simcore_service_autoscaling.utils.utils_docker import (
    _OSPARC_SERVICE_READY_LABEL_KEY,
    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
)
from tenacity import after_log, before_sleep_log, retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType
from types_aiobotocore_ec2.type_defs import TagTypeDef

pytest_plugins = [
    "pytest_simcore.asyncio_event_loops",
    "pytest_simcore.aws_server",
    "pytest_simcore.aws_ec2_service",
    "pytest_simcore.aws_iam_service",
    "pytest_simcore.aws_ssm_service",
    "pytest_simcore.dask_scheduler",
    "pytest_simcore.docker",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.rabbit_service",
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
def mocked_ec2_server_envs(
    mocked_ec2_server_settings: EC2Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # NOTE: overrides the EC2Settings with what autoscaling expects
    changed_envs: EnvVarsDict = {
        f"{AUTOSCALING_ENV_PREFIX}{k}": v
        for k, v in mocked_ec2_server_settings.model_dump().items()
    }
    return setenvs_from_dict(monkeypatch, changed_envs)  # type: ignore


@pytest.fixture(
    params=[
        "with_AUTOSCALING_DRAIN_NODES_WITH_LABELS",
        "without_AUTOSCALING_DRAIN_NODES_WITH_LABELS",
    ]
)
def with_drain_nodes_labelled(request: pytest.FixtureRequest) -> bool:
    return bool(request.param == "with_AUTOSCALING_DRAIN_NODES_WITH_LABELS")


@pytest.fixture
def with_labelize_drain_nodes(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    with_drain_nodes_labelled: bool,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "AUTOSCALING_DRAIN_NODES_WITH_LABELS": f"{with_drain_nodes_labelled}",
        },
    )


@pytest.fixture(
    params=[
        "with_AUTOSCALING_DOCKER_JOIN_DRAINED",
        "without_AUTOSCALING_DOCKER_JOIN_DRAINED",
    ]
)
def with_docker_join_drained(request: pytest.FixtureRequest) -> bool:
    return bool(request.param == "with_AUTOSCALING_DOCKER_JOIN_DRAINED")


@pytest.fixture
def app_with_docker_join_drained(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    with_docker_join_drained: bool,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "AUTOSCALING_DOCKER_JOIN_DRAINED": f"{with_docker_join_drained}",
        },
    )


@pytest.fixture(scope="session")
def fake_ssm_settings() -> SSMSettings:
    assert "json_schema_extra" in SSMSettings.model_config
    assert isinstance(SSMSettings.model_config["json_schema_extra"], dict)
    assert isinstance(SSMSettings.model_config["json_schema_extra"]["examples"], list)
    return SSMSettings.model_validate(
        SSMSettings.model_config["json_schema_extra"]["examples"][0]
    )


@pytest.fixture
def ec2_settings() -> EC2Settings:
    return AutoscalingEC2Settings.create_from_envs()


@pytest.fixture
def ec2_instance_custom_tags(
    faker: Faker,
    external_envfile_dict: EnvVarsDict,
) -> dict[str, str]:
    if external_envfile_dict:
        return json.loads(external_envfile_dict["EC2_INSTANCES_CUSTOM_TAGS"])
    return {"osparc-tag": faker.text(max_nb_chars=80), "pytest": faker.pystr()}


@pytest.fixture
def external_ec2_instances_allowed_types(
    external_envfile_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None | dict[str, EC2InstanceBootSpecific]:
    if not external_envfile_dict:
        return None
    with monkeypatch.context() as patch:
        setenvs_from_dict(patch, {**external_envfile_dict})
        settings = EC2InstancesSettings.create_from_envs()
    return settings.EC2_INSTANCES_ALLOWED_TYPES


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    aws_allowed_ec2_instance_type_names: list[InstanceTypeType],
    ec2_instance_custom_tags: dict[str, str],
    external_envfile_dict: EnvVarsDict,
) -> EnvVarsDict:
    # SEE https://faker.readthedocs.io/en/master/providers/faker.providers.internet.html?highlight=internet#faker-providers-internet
    if external_envfile_dict:
        delenvs_from_dict(monkeypatch, mock_env_devel_environment, raising=False)
        return setenvs_from_dict(monkeypatch, {**external_envfile_dict})

    assert "json_schema_extra" in EC2InstanceBootSpecific.model_config
    assert isinstance(EC2InstanceBootSpecific.model_config["json_schema_extra"], dict)
    assert isinstance(
        EC2InstanceBootSpecific.model_config["json_schema_extra"]["examples"], list
    )
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "AUTOSCALING_EC2_ACCESS": "{}",
            "AUTOSCALING_EC2_ACCESS_KEY_ID": faker.pystr(),
            "AUTOSCALING_EC2_SECRET_ACCESS_KEY": faker.pystr(),
            "AUTOSCALING_EC2_INSTANCES": "{}",
            "AUTOSCALING_SSM_ACCESS": "{}",
            "AUTOSCALING_TRACING": "null",
            "SSM_ACCESS_KEY_ID": faker.pystr(),
            "SSM_SECRET_ACCESS_KEY": faker.pystr(),
            "EC2_INSTANCES_KEY_NAME": faker.pystr(),
            "EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    ec2_type_name: random.choice(  # noqa: S311
                        EC2InstanceBootSpecific.model_config["json_schema_extra"][
                            "examples"
                        ]
                    )
                    for ec2_type_name in aws_allowed_ec2_instance_type_names
                }
            ),
            "EC2_INSTANCES_CUSTOM_TAGS": json.dumps(ec2_instance_custom_tags),
            "EC2_INSTANCES_ATTACHED_IAM_PROFILE": faker.pystr(),
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
    aws_instance_profile: str,
) -> EnvVarsDict:
    assert "json_schema_extra" in EC2InstanceBootSpecific.model_config
    assert isinstance(EC2InstanceBootSpecific.model_config["json_schema_extra"], dict)
    assert isinstance(
        EC2InstanceBootSpecific.model_config["json_schema_extra"]["examples"], list
    )
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_KEY_NAME": "osparc-pytest",
            "EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps([aws_security_group_id]),
            "EC2_INSTANCES_SUBNET_ID": aws_subnet_id,
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    ec2_type_name: cast(
                        dict,
                        random.choice(  # noqa: S311
                            EC2InstanceBootSpecific.model_config["json_schema_extra"][
                                "examples"
                            ]
                        ),
                    )
                    | {"ami_id": aws_ami_id}
                    for ec2_type_name in aws_allowed_ec2_instance_type_names
                }
            ),
            "EC2_INSTANCES_ATTACHED_IAM_PROFILE": aws_instance_profile,
        },
    )
    return app_environment | envs


@pytest.fixture
def disable_autoscaling_background_task(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_autoscaling.modules.cluster_scaling.auto_scaling_task.create_periodic_task",
        autospec=True,
    )

    mocker.patch(
        "simcore_service_autoscaling.modules.cluster_scaling.auto_scaling_task.cancel_wait_task",
        autospec=True,
    )


@pytest.fixture
def disable_buffers_pool_background_task(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_autoscaling.modules.cluster_scaling.buffer_machines_pool_task.create_periodic_task",
        autospec=True,
    )

    mocker.patch(
        "simcore_service_autoscaling.modules.cluster_scaling.buffer_machines_pool_task.cancel_wait_task",
        autospec=True,
    )


@pytest.fixture
def with_enabled_buffer_pools(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "AUTOSCALING_SSM_ACCESS": "{}",
        },
    )


@pytest.fixture
def enabled_dynamic_mode(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
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
            "DASK_SCHEDULER_AUTH": "{}",
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
def disabled_ssm(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOSCALING_SSM_ACCESS", "null")


@pytest.fixture
def enabled_rabbitmq(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitSettings:
    return rabbit_service


_LIFESPAN_TIMEOUT: Final[int] = 10


@pytest.fixture
async def initialized_app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    # NOTE: the timeout is sometime too small for CI machines, and even larger machines
    async with LifespanManager(
        app, startup_timeout=_LIFESPAN_TIMEOUT, shutdown_timeout=_LIFESPAN_TIMEOUT
    ):
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
    return dict.fromkeys(
        app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
        "true",
    )


@pytest.fixture
async def async_client(initialized_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=initialized_app),
        base_url=f"http://{initialized_app.title}.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
async def autoscaling_docker() -> AsyncIterator[AutoscalingDocker]:
    async with AutoscalingDocker() as docker_client:
        yield cast(AutoscalingDocker, docker_client)


@pytest.fixture
async def host_node(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
) -> AsyncIterator[DockerNode]:
    nodes = TypeAdapter(list[DockerNode]).validate_python(
        await async_docker_client.nodes.list()
    )
    assert len(nodes) == 1
    # keep state of node for later revert
    old_node = deepcopy(nodes[0])
    assert old_node.id
    assert old_node.spec
    assert old_node.spec.role
    assert old_node.spec.availability
    assert old_node.version
    assert old_node.version.index
    labels = old_node.spec.labels or {}
    # ensure we have the necessary labels
    await async_docker_client.nodes.update(
        node_id=old_node.id,
        version=old_node.version.index,
        spec={
            "Availability": old_node.spec.availability.value,
            "Labels": labels
            | {
                _OSPARC_SERVICE_READY_LABEL_KEY: "true",
                _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: arrow.utcnow().isoformat(),
            },
            "Role": old_node.spec.role.value,
        },
    )
    modified_host_node = TypeAdapter(DockerNode).validate_python(
        await async_docker_client.nodes.inspect(node_id=old_node.id)
    )
    yield modified_host_node
    # revert state
    current_node = TypeAdapter(DockerNode).validate_python(
        await async_docker_client.nodes.inspect(node_id=old_node.id)
    )
    assert current_node.id
    assert current_node.version
    assert current_node.version.index
    await async_docker_client.nodes.update(
        node_id=current_node.id,
        version=current_node.version.index,
        spec={
            "Availability": old_node.spec.availability.value,
            "Labels": old_node.spec.labels,
            "Role": old_node.spec.role.value,
        },
    )


@pytest.fixture
def create_fake_node(faker: Faker) -> Callable[..., DockerNode]:
    def _creator(**node_overrides) -> DockerNode:
        default_config = {
            "ID": faker.uuid4(),
            "Version": ObjectVersion(index=faker.pyint()),
            "CreatedAt": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            "UpdatedAt": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            "Description": NodeDescription(
                hostname=faker.pystr(),
                resources=ResourceObject(
                    nano_cp_us=int(9 * 1e9),
                    memory_bytes=TypeAdapter(ByteSize).validate_python("256GiB"),
                ),
            ),
            "Spec": NodeSpec(
                name=None,
                labels=faker.pydict(allowed_types=(str,)),
                role=None,
                availability=Availability.drain,
            ),
            "Status": NodeStatus(state=NodeState.unknown, message=None, addr=None),
        }
        default_config.update(**node_overrides)
        return DockerNode(**default_config)

    return _creator


@pytest.fixture
def fake_node(create_fake_node: Callable[..., DockerNode]) -> DockerNode:
    return create_fake_node()


@pytest.fixture
def task_template() -> dict[str, Any]:
    return {
        "ContainerSpec": {
            "Image": "redis:7.0.5-alpine",
        },
    }


_GIGA_NANO_CPU = 10**9
NUM_CPUS: TypeAlias = PositiveInt


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
        base_labels: dict[DockerLabelKey, Any] = {}
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
        with log_context(
            logging.INFO, msg=f"create docker service {service_name}"
        ) as ctx:
            service = await async_docker_client.services.create(
                task_template=task_template,
                name=service_name,
                labels=base_labels,  # type: ignore
            )
            assert service
            service = TypeAdapter(Service).validate_python(
                await async_docker_client.services.inspect(service["ID"])
            )
            assert service.spec
            ctx.logger.info(
                "%s",
                f"service {service.id} with {service.spec.name} created",
            )
        assert service.spec.labels == base_labels

        created_services.append(service)
        # get more info on that service

        assert service.spec.name == service_name

        original_task_template_model = TypeAdapter(TaskSpec).validate_python(
            task_template
        )

        excluded_paths = {
            "force_update",
            "runtime",
            "root['container_spec']['isolation']",
        }
        if not base_labels:
            excluded_paths.add("root['container_spec']['labels']")
        for reservation in ["memory_bytes", "nano_cp_us"]:
            if (
                original_task_template_model.resources
                and original_task_template_model.resources.reservations
                and getattr(
                    original_task_template_model.resources.reservations, reservation
                )
                == 0
            ):
                # NOTE: if a 0 memory reservation is done, docker removes it from the task inspection
                excluded_paths.add(
                    f"root['resources']['reservations']['{reservation}']"
                )

        assert service.spec.task_template
        diff = DeepDiff(
            original_task_template_model.model_dump(exclude_unset=True),
            service.spec.task_template.model_dump(exclude_unset=True),
            exclude_paths=list(excluded_paths),
        )
        assert not diff, f"{diff}"
        assert service.spec.labels == base_labels
        await _assert_wait_for_service_state(
            async_docker_client, service, [wait_for_service_state]
        )
        return service

    yield _creator

    await asyncio.gather(
        *(async_docker_client.services.delete(s.id) for s in created_services),
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
        assert service.spec
        with log_context(
            logging.INFO,
            msg=f"check service {service.id}:{service.spec.name} is really gone",
        ):
            assert not await async_docker_client.containers.list(
                all=True,
                filters={
                    "label": [f"com.docker.swarm.service.id={service.id}"],
                },
            )

    await asyncio.gather(*(_check_service_task_gone(s) for s in created_services))
    await asyncio.sleep(0)


SUCCESS_STABLE_TIME_S: Final[float] = 3
WAIT_TIME: Final[float] = 0.5


async def _assert_wait_for_service_state(
    async_docker_client: aiodocker.Docker, service: Service, expected_states: list[str]
) -> None:
    with log_context(
        logging.INFO, msg=f"wait for service {service.id} to become {expected_states}"
    ) as ctx:
        number_of_success = {"count": 0}

        @retry(
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
            wait=wait_fixed(WAIT_TIME),
            stop=stop_after_delay(10 * SUCCESS_STABLE_TIME_S),
            before_sleep=before_sleep_log(ctx.logger, logging.DEBUG),
            after=after_log(ctx.logger, logging.DEBUG),
        )
        async def _() -> None:
            assert service.id
            services = await async_docker_client.services.list(
                filters={"id": service.id}
            )
            assert services, f"no service with {service.id}!"
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
            ctx.logger.info(
                "%s",
                f"service {found_service['Spec']['Name']} is now {service_task['Status']['State']} {'.' * number_of_success['count']}",
            )
            number_of_success["count"] += 1
            assert (number_of_success["count"] * WAIT_TIME) >= SUCCESS_STABLE_TIME_S
            ctx.logger.info(
                "%s",
                f"service {found_service['Spec']['Name']} is now {service_task['Status']['State']} after {SUCCESS_STABLE_TIME_S} seconds",
            )

        await _()


@pytest.fixture(scope="session")
def aws_allowed_ec2_instance_type_names() -> list[InstanceTypeType]:
    return [
        "t2.xlarge",
        "t2.2xlarge",
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
    changed_envs: dict[str, str | bool] = {
        "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(aws_allowed_ec2_instance_type_names),
    }
    return app_environment | setenvs_from_dict(monkeypatch, changed_envs)


@pytest.fixture
def host_cpu_count() -> int:
    cpus = psutil.cpu_count()
    assert cpus is not None
    return cpus


@pytest.fixture
def host_memory_total() -> ByteSize:
    return ByteSize(psutil.virtual_memory().total)


@pytest.fixture
def osparc_docker_label_keys(
    faker: Faker,
) -> StandardSimcoreDockerLabels:
    return StandardSimcoreDockerLabels.model_validate(
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
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
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
                pending_nodes=[],
                drained_nodes=[],
                buffer_drained_nodes=[],
                pending_ec2s=[],
                broken_ec2s=[],
                buffer_ec2s=[],
                disconnected_nodes=[],
                terminating_nodes=[],
                retired_nodes=[],
                terminated_instances=[],
            ),
            **cluter_overrides,
        )

    return _creator


@pytest.fixture
async def create_dask_task(
    dask_spec_cluster_client: distributed.Client,
) -> Callable[..., distributed.Future]:
    def _remote_pytest_fct(x: int, y: int) -> int:
        return x + y

    def _creator(
        required_resources: DaskTaskResources, **overrides
    ) -> distributed.Future:
        # NOTE: pure will ensure dask does not re-use the task results if we run it several times
        future = dask_spec_cluster_client.submit(
            _remote_pytest_fct,
            23,
            43,
            resources=required_resources,
            pure=False,
            **overrides,
        )
        assert future
        return future

    return _creator


@pytest.fixture
def mock_docker_set_node_availability(mocker: MockerFixture) -> mock.Mock:
    async def _fake_set_node_availability(
        docker_client: AutoscalingDocker, node: DockerNode, *, available: bool
    ) -> DockerNode:
        returned_node = deepcopy(node)
        assert returned_node.spec
        returned_node.spec.availability = (
            Availability.active if available else Availability.drain
        )
        returned_node.updated_at = datetime.datetime.now(tz=datetime.UTC).isoformat()
        return returned_node

    return mocker.patch(
        "simcore_service_autoscaling.modules.cluster_scaling._auto_scaling_core.utils_docker.set_node_availability",
        autospec=True,
        side_effect=_fake_set_node_availability,
    )


@pytest.fixture
def mock_docker_tag_node(mocker: MockerFixture) -> mock.Mock:
    async def fake_tag_node(
        docker_client: AutoscalingDocker,
        node: DockerNode,
        *,
        tags: dict[DockerLabelKey, str],
        available: bool,
    ) -> DockerNode:
        updated_node = deepcopy(node)
        assert updated_node.spec
        updated_node.spec.labels = deepcopy(cast(dict[str, str], tags))
        updated_node.spec.availability = (
            Availability.active if available else Availability.drain
        )
        return updated_node

    return mocker.patch(
        "simcore_service_autoscaling.modules.cluster_scaling._auto_scaling_core.utils_docker.tag_node",
        autospec=True,
        side_effect=fake_tag_node,
    )


@pytest.fixture
def patch_ec2_client_launch_instances_min_number_of_instances(
    mocker: MockerFixture,
) -> mock.Mock:
    """the moto library always returns min number of instances instead of max number of instances which makes
    it difficult to test scaling to multiple of machines. this should help"""
    original_fct = SimcoreEC2API.launch_instances

    async def _change_parameters(*args, **kwargs) -> list[EC2InstanceData]:
        new_kwargs = kwargs | {"min_number_of_instances": kwargs["number_of_instances"]}
        print(f"patching launch_instances with: {new_kwargs}")
        return await original_fct(*args, **new_kwargs)

    return mocker.patch.object(
        SimcoreEC2API,
        "launch_instances",
        autospec=True,
        side_effect=_change_parameters,
    )


@pytest.fixture
def random_fake_available_instances(faker: Faker) -> list[EC2InstanceType]:
    list_of_instances = [
        EC2InstanceType(
            name=random.choice(get_args(InstanceTypeType)),  # noqa: S311
            resources=Resources(cpus=n, ram=ByteSize(n)),
        )
        for n in range(1, 30)
    ]
    random.shuffle(list_of_instances)
    return list_of_instances


@pytest.fixture
def create_associated_instance(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    app_settings: ApplicationSettings,
    faker: Faker,
    host_cpu_count: int,
    host_memory_total: ByteSize,
) -> Callable[[DockerNode, bool, dict[str, Any]], AssociatedInstance]:
    def _creator(
        node: DockerNode,
        terminateable_time: bool,
        fake_ec2_instance_data_override: dict[str, Any] | None = None,
    ) -> AssociatedInstance:
        assert app_settings.AUTOSCALING_EC2_INSTANCES
        assert (
            datetime.timedelta(seconds=10)
            < app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        ), "this tests relies on the fact that the time before termination is above 10 seconds"
        assert app_settings.AUTOSCALING_EC2_INSTANCES
        seconds_delta = (
            -datetime.timedelta(seconds=10)
            if terminateable_time
            else datetime.timedelta(seconds=10)
        )

        if fake_ec2_instance_data_override is None:
            fake_ec2_instance_data_override = {}

        return AssociatedInstance(
            node=node,
            ec2_instance=fake_ec2_instance_data(
                launch_time=datetime.datetime.now(datetime.UTC)
                - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
                - datetime.timedelta(
                    days=faker.pyint(min_value=0, max_value=100),
                    hours=faker.pyint(min_value=0, max_value=100),
                )
                + seconds_delta,
                resources=Resources(cpus=host_cpu_count, ram=host_memory_total),
                **fake_ec2_instance_data_override,
            ),
        )

    return _creator


@pytest.fixture
def num_hot_buffer() -> NonNegativeInt:
    return 5


@pytest.fixture
def with_instances_machines_hot_buffer(
    num_hot_buffer: int,
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_MACHINES_BUFFER": f"{num_hot_buffer}",
        },
    )


@pytest.fixture
def hot_buffer_instance_type(app_settings: ApplicationSettings) -> InstanceTypeType:
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    return cast(
        InstanceTypeType,
        next(iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)),
    )


@pytest.fixture
def mock_find_node_with_name_returns_none(mocker: MockerFixture) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.cluster_scaling._auto_scaling_core.utils_docker.find_node_with_name",
        autospec=True,
        return_value=None,
    )


@pytest.fixture(scope="session")
def short_ec2_instance_max_start_time() -> datetime.timedelta:
    return datetime.timedelta(seconds=10)


@pytest.fixture
def with_short_ec2_instances_max_start_time(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    short_ec2_instance_max_start_time: datetime.timedelta,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_MAX_START_TIME": f"{short_ec2_instance_max_start_time}",
        },
    )


@pytest.fixture
async def spied_cluster_analysis(mocker: MockerFixture) -> MockType:
    return mocker.spy(_auto_scaling_core, "_analyze_current_cluster")


@pytest.fixture
async def mocked_associate_ec2_instances_with_nodes(mocker: MockerFixture) -> mock.Mock:
    async def _(
        nodes: list[DockerNode], ec2_instances: list[EC2InstanceData]
    ) -> tuple[list[AssociatedInstance], list[EC2InstanceData]]:
        return [], ec2_instances

    return mocker.patch(
        "simcore_service_autoscaling.modules.cluster_scaling._auto_scaling_core.associate_ec2_instances_with_nodes",
        autospec=True,
        side_effect=_,
    )


@pytest.fixture
def fake_pre_pull_images() -> list[DockerGenericTag]:
    return TypeAdapter(list[DockerGenericTag]).validate_python(
        [
            "nginx:latest",
            "itisfoundation/my-very-nice-service:latest",
            "simcore/services/dynamic/another-nice-one:2.4.5",
            "asd",
        ]
    )


@pytest.fixture
def ec2_instances_allowed_types_with_only_1_buffered(
    faker: Faker,
    fake_pre_pull_images: list[DockerGenericTag],
    external_ec2_instances_allowed_types: None | dict[str, EC2InstanceBootSpecific],
) -> dict[InstanceTypeType, EC2InstanceBootSpecific]:
    if not external_ec2_instances_allowed_types:
        return {
            "t2.micro": EC2InstanceBootSpecific(
                ami_id=faker.pystr(),
                pre_pull_images=fake_pre_pull_images,
                buffer_count=faker.pyint(min_value=2, max_value=10),
            )
        }

    allowed_ec2_types = external_ec2_instances_allowed_types
    allowed_ec2_types_with_buffer_defined = dict(
        filter(
            lambda instance_type_and_settings: instance_type_and_settings[
                1
            ].buffer_count
            > 0,
            allowed_ec2_types.items(),
        )
    )
    assert (
        allowed_ec2_types_with_buffer_defined
    ), "one type with buffer is needed for the tests!"
    assert (
        len(allowed_ec2_types_with_buffer_defined) == 1
    ), "more than one type with buffer is disallowed in this test!"
    return {
        TypeAdapter(InstanceTypeType).validate_python(k): v
        for k, v in allowed_ec2_types_with_buffer_defined.items()
    }


@pytest.fixture
def buffer_count(
    ec2_instances_allowed_types_with_only_1_buffered: dict[
        InstanceTypeType, EC2InstanceBootSpecific
    ],
) -> int:
    def _by_buffer_count(
        instance_type_and_settings: tuple[InstanceTypeType, EC2InstanceBootSpecific],
    ) -> bool:
        _, boot_specific = instance_type_and_settings
        return boot_specific.buffer_count > 0

    allowed_ec2_types = ec2_instances_allowed_types_with_only_1_buffered
    allowed_ec2_types_with_buffer_defined = dict(
        filter(_by_buffer_count, allowed_ec2_types.items())
    )
    assert allowed_ec2_types_with_buffer_defined, "you need one type with buffer"
    assert (
        len(allowed_ec2_types_with_buffer_defined) == 1
    ), "more than one type with buffer is disallowed in this test!"
    return next(iter(allowed_ec2_types_with_buffer_defined.values())).buffer_count


@pytest.fixture
async def create_buffer_machines(
    ec2_client: EC2Client,
    aws_ami_id: str,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
) -> Callable[
    [int, InstanceTypeType, InstanceStateNameType, list[DockerGenericTag] | None],
    Awaitable[list[str]],
]:
    async def _do(
        num: int,
        instance_type: InstanceTypeType,
        instance_state_name: InstanceStateNameType,
        pre_pull_images: list[DockerGenericTag] | None,
    ) -> list[str]:
        assert app_settings.AUTOSCALING_EC2_INSTANCES

        assert instance_state_name in [
            "running",
            "stopped",
        ], "only 'running' and 'stopped' are supported for testing"

        resource_tags: list[TagTypeDef] = [
            {"Key": tag_key, "Value": tag_value}
            for tag_key, tag_value in get_deactivated_buffer_ec2_tags(
                DynamicAutoscalingProvider().get_ec2_tags(initialized_app)
            ).items()
        ]
        if pre_pull_images is not None and instance_state_name == "stopped":
            resource_tags.append(
                {
                    "Key": PRE_PULLED_IMAGES_EC2_TAG_KEY,
                    "Value": f"{json_dumps(pre_pull_images)}",
                }
            )
        with log_context(
            logging.INFO, f"creating {num} buffer machines of {instance_type}"
        ):
            instances = await ec2_client.run_instances(
                ImageId=aws_ami_id,
                MaxCount=num,
                MinCount=num,
                InstanceType=instance_type,
                KeyName=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME,
                SecurityGroupIds=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SECURITY_GROUP_IDS,
                SubnetId=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SUBNET_ID,
                IamInstanceProfile={
                    "Arn": app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ATTACHED_IAM_PROFILE
                },
                TagSpecifications=[
                    {"ResourceType": "instance", "Tags": resource_tags},
                    {"ResourceType": "volume", "Tags": resource_tags},
                    {"ResourceType": "network-interface", "Tags": resource_tags},
                ],
                UserData="echo 'I am pytest'",
            )
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

        if instance_state_name == "stopped":
            await ec2_client.stop_instances(InstanceIds=instance_ids)
            instances = await ec2_client.describe_instances(InstanceIds=instance_ids)
            assert "Reservations" in instances
            assert instances["Reservations"]
            assert "Instances" in instances["Reservations"][0]
            assert len(instances["Reservations"][0]["Instances"]) == num
            for instance in instances["Reservations"][0]["Instances"]:
                assert "State" in instance
                assert "Name" in instance["State"]
                assert instance["State"]["Name"] == "stopped"

        return instance_ids

    return _do
