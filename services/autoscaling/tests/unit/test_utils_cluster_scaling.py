# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import datetime
import json
import secrets
from collections.abc import Callable
from pathlib import Path
from random import choice, shuffle

import arrow
import pytest
from aws_library.ec2 import EC2InstanceType
from faker import Faker
from models_library.docker import DockerGenericTag
from models_library.generated_models.docker_rest_api import Node as DockerNode
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_ec2_boot import BootScriptRunner
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import AssociatedInstance, EC2InstanceData
from simcore_service_autoscaling.utils.cluster_scaling import (
    associate_ec2_instances_with_nodes,
    ec2_startup_script,
    sort_drained_nodes,
)
from simcore_service_autoscaling.utils.utils_docker import (
    _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY,
    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
)
from types_aiobotocore_ec2.literals import InstanceTypeType


def _find_boot_steps(startup_script: str) -> list[str]:
    return startup_script.split(" && ")


@pytest.fixture
def node(faker: Faker) -> Callable[..., DockerNode]:
    def _creator(**overrides) -> DockerNode:
        return DockerNode(
            **(
                {
                    "ID": faker.uuid4(),
                    "CreatedAt": f"{faker.date_time()}",
                    "UpdatedAt": f"{faker.date_time()}",
                    "Description": {"Hostname": faker.pystr()},
                }
                | overrides
            )
        )

    return _creator


@pytest.mark.parametrize("valid_ec2_dns", [True, False])
async def test_associate_ec2_instances_with_nodes_with_no_correspondence(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., DockerNode],
    valid_ec2_dns: bool,
):
    nodes = [node() for _ in range(10)]
    ec2_instances = [
        (
            fake_ec2_instance_data(aws_private_dns=f"ip-10-12-32-{n + 1}.internal-data")
            if valid_ec2_dns
            else fake_ec2_instance_data()
        )
        for n in range(10)
    ]

    (
        associated_instances,
        non_associated_instances,
    ) = associate_ec2_instances_with_nodes(nodes, ec2_instances)

    assert not associated_instances
    assert non_associated_instances
    assert len(non_associated_instances) == len(ec2_instances)


async def test_associate_ec2_instances_with_nodes_with_invalid_dns(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., DockerNode],
):
    nodes = [node() for _ in range(10)]
    ec2_instances = [fake_ec2_instance_data(aws_private_dns="invalid-dns-name") for _ in range(10)]

    (
        associated_instances,
        non_associated_instances,
    ) = associate_ec2_instances_with_nodes(nodes, ec2_instances)

    assert not associated_instances
    assert non_associated_instances


async def test_associate_ec2_instances_with_corresponding_nodes(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., DockerNode],
):
    nodes = []
    ec2_instances = []
    for n in range(10):
        host_name = f"ip-10-12-32-{n + 1}"
        nodes.append(node(Description={"Hostname": host_name}))
        ec2_instances.append(fake_ec2_instance_data(aws_private_dns=f"{host_name}.internal-data"))

    (
        associated_instances,
        non_associated_instances,
    ) = associate_ec2_instances_with_nodes(nodes, ec2_instances)

    assert associated_instances
    assert not non_associated_instances
    assert len(associated_instances) == len(ec2_instances)
    assert len(associated_instances) == len(nodes)
    for associated_instance in associated_instances:
        assert associated_instance.node.description
        assert associated_instance.node.description.hostname
        assert associated_instance.node.description.hostname in associated_instance.ec2_instance.aws_private_dns


@pytest.fixture
def minimal_configuration(
    docker_swarm: None,
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    disable_autoscaling_background_task: None,
    mocked_redis_server: None,
) -> None: ...


@pytest.fixture
def ec2_instances_boot_just_ami(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps({"t2.micro": {"ami_id": faker.pystr()}}),
        },
    )
    return app_environment | envs


async def test_ec2_startup_script_just_ami(
    minimal_configuration: None,
    ec2_instances_boot_just_ami: EnvVarsDict,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_boot_specific = next(iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()))
    assert not instance_boot_specific.pre_pull_images
    startup_script = await ec2_startup_script(instance_boot_specific, app_settings)

    steps = _find_boot_steps(startup_script)
    assert len(steps) == 2, f"expected a login and a swarm join, got {steps}"
    assert " docker login " in steps[0], f"expected the machine to log in before joining, got {steps[0]}"
    assert steps[-1].startswith("docker swarm join --availability=drain --token "), (
        f"expected the last step to join the swarm, got {steps[-1]}"
    )


@pytest.fixture
def ec2_instances_boot_ami_scripts(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> list[str]:
    custom_scripts = faker.pylist(allowed_types=(str,))
    setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    "t2.micro": {
                        "ami_id": faker.pystr(),
                        "custom_boot_scripts": custom_scripts,
                    }
                }
            ),
        },
    )
    return custom_scripts


@pytest.fixture
def ec2_instances_boot_ami_pre_pull(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> EnvVarsDict:
    images = TypeAdapter(list[DockerGenericTag]).validate_python(
        [
            "nginx:latest",
            "itisfoundation/my-very-nice-service:latest",
            "simcore/services/dynamic/another-nice-one:2.4.5",
            "asd",
        ]
    )
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {"t2.micro": {"ami_id": faker.pystr(), "pre_pull_images": images}}
            ),
        },
    )
    return app_environment | envs


@pytest.fixture
def disabled_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGISTRY_AUTH")


@pytest.fixture
def anonymous_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRY_AUTH", "False")


async def test_ec2_startup_script_with_pre_pulling(
    minimal_configuration: None,
    ec2_instances_boot_ami_pre_pull: EnvVarsDict,
    with_ec2_instances_cold_start_docker_images_pre_pulling: EnvVarsDict,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_boot_specific = next(iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()))
    assert instance_boot_specific.pre_pull_images
    startup_script = await ec2_startup_script(instance_boot_specific, app_settings)

    steps = _find_boot_steps(startup_script)
    login = next(step for step in steps if " docker login " in step)
    join = next(step for step in steps if step.startswith("docker swarm join "))
    assert login.startswith("( "), f"expected the login to retry in a subshell, got {login}"
    pull = next(index for index, step in enumerate(steps) if step == "./docker-pull-script.sh")
    # the machine logs in before it can be accepted into the cluster, and pulls only after joining
    assert steps.index(login) < steps.index(join) < pull, f"expected login, join, pull, got {steps}"


async def test_ec2_startup_script_logs_in_before_joining_the_swarm(
    minimal_configuration: None,
    ec2_instances_boot_ami_pre_pull: EnvVarsDict,
    with_ec2_instances_cold_start_docker_images_pre_pulling: EnvVarsDict,
    app_settings: ApplicationSettings,
    tmp_path: Path,
    run_as_if_in_ec2: BootScriptRunner,
):
    """A machine that cannot log in must not join the swarm

    The service accepts a machine as soon as it sees its swarm node, so a machine joining without registry
    credentials gets tasks it cannot pull. This is the behaviour private-issues#703 is about, hence running
    the boot script instead of only reading it.
    """
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_boot_specific = next(iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()))
    startup_script = await ec2_startup_script(instance_boot_specific, app_settings)

    docker_calls_log_path = tmp_path / "docker-calls.log"
    result = run_as_if_in_ec2(
        startup_script,
        {
            "docker": """#!/usr/bin/env bash
echo "$*" >> "$DOCKER_CALLS_LOG"
test "$1" != login
"""
        },
        {"DOCKER_CALLS_LOG": str(docker_calls_log_path)},
    )

    assert result.returncode != 0, result.stderr
    logged_docker_calls = docker_calls_log_path.read_text() if docker_calls_log_path.exists() else ""
    assert "login" in logged_docker_calls, "the boot script never tried to log in"
    assert "swarm join" not in logged_docker_calls, "the machine joined the swarm without credentials"


async def test_ec2_startup_script_with_custom_scripts(
    minimal_configuration: None,
    ec2_instances_boot_ami_scripts: list[str],
    app_settings: ApplicationSettings,
):
    for _ in range(3):
        assert app_settings.AUTOSCALING_EC2_INSTANCES
        instance_boot_specific = next(iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()))
        assert not instance_boot_specific.pre_pull_images
        startup_script = await ec2_startup_script(instance_boot_specific, app_settings)

        steps = _find_boot_steps(startup_script)
        num_custom_scripts = len(ec2_instances_boot_ami_scripts)
        assert steps[:num_custom_scripts] == ec2_instances_boot_ami_scripts, (
            f"expected the custom boot scripts first, got {steps}"
        )
        assert " docker login " in steps[num_custom_scripts], (
            f"expected the machine to log in after the custom scripts, got {steps}"
        )
        assert steps[-1].startswith("docker swarm join "), f"expected the last step to join the swarm, got {steps[-1]}"


async def test_ec2_startup_script_with_pre_pulling_but_no_registry(
    minimal_configuration: None,
    ec2_instances_boot_ami_pre_pull: EnvVarsDict,
    disabled_registry: None,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_boot_specific = next(iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()))
    assert instance_boot_specific.pre_pull_images
    startup_script = await ec2_startup_script(instance_boot_specific, app_settings)

    steps = _find_boot_steps(startup_script)
    assert len(steps) == 1, f"expected only a swarm join without a registry, got {steps}"
    assert steps[0].startswith("docker swarm join "), f"expected the machine to join the swarm, got {steps[0]}"
    assert "docker login" not in startup_script, f"expected no login without a registry, got {startup_script}"


async def test_ec2_startup_script_with_pre_pulling_but_anonymous_registry(
    minimal_configuration: None,
    ec2_instances_boot_ami_pre_pull: EnvVarsDict,
    with_ec2_instances_cold_start_docker_images_pre_pulling: EnvVarsDict,
    anonymous_registry: None,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert app_settings.AUTOSCALING_REGISTRY
    assert not app_settings.AUTOSCALING_REGISTRY.REGISTRY_AUTH
    instance_boot_specific = next(iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()))
    assert instance_boot_specific.pre_pull_images
    startup_script = await ec2_startup_script(instance_boot_specific, app_settings)

    steps = _find_boot_steps(startup_script)
    # images pull without credentials here, so a login failure must not keep the machine out of the swarm
    assert "docker login" not in startup_script, f"expected no login without registry authentication, got {steps}"
    join = next(step for step in steps if step.startswith("docker swarm join "))
    pull = next(index for index, step in enumerate(steps) if step == "./docker-pull-script.sh")
    assert steps.index(join) < pull, f"expected the machine to join before pulling, got {steps}"


def test_sort_empty_drained_nodes(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
):
    assert sort_drained_nodes(app_settings, []) == (
        [],
        [],
        [],
    )


def test_sort_drained_nodes(
    minimal_configuration: None,
    with_multiple_hot_buffer_instance_types: EnvVarsDict,
    app_settings: ApplicationSettings,
    random_fake_available_instances: list[EC2InstanceType],
    create_fake_node: Callable[..., DockerNode],
    create_associated_instance: Callable[..., AssociatedInstance],
    hot_buffer_instance_types: set[InstanceTypeType],
    hot_buffer_total_count: int,
):
    assert len(hot_buffer_instance_types) > 0, "this test needs at least 2 hot buffer instance types configured"
    assert app_settings.AUTOSCALING_EC2_INSTANCES

    _NUM_DRAINED_NODES = 20
    _RATIO_HOT_BUFFER_TYPES = 3
    _NUM_NODES_TERMINATING = 13
    fake_drained_nodes = []
    for _ in range(_NUM_DRAINED_NODES):
        fake_node = create_fake_node()
        fake_associated_instance = create_associated_instance(
            fake_node,
            terminateable_time=False,
            fake_ec2_instance_data_override={
                "type": choice(  # noqa: S311
                    [i for i in random_fake_available_instances if i not in hot_buffer_instance_types]
                ).name
            },
        )
        fake_drained_nodes.append(fake_associated_instance)

    for hot_buffer_type in hot_buffer_instance_types:
        for _ in range(
            _RATIO_HOT_BUFFER_TYPES
            * app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[hot_buffer_type].hot_buffer_count
        ):
            fake_node = create_fake_node()
            fake_associated_instance = create_associated_instance(
                fake_node,
                terminateable_time=False,
                fake_ec2_instance_data_override={"type": hot_buffer_type},
            )
            fake_drained_nodes.append(fake_associated_instance)

    for _ in range(_NUM_NODES_TERMINATING):
        fake_node = create_fake_node()
        assert fake_node.spec
        assert fake_node.spec.labels
        fake_node.spec.labels[_OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY] = arrow.utcnow().datetime.isoformat()
        fake_associated_instance = create_associated_instance(
            fake_node,
            terminateable_time=False,
            fake_ec2_instance_data_override={"type": secrets.choice(tuple(hot_buffer_instance_types))},
        )
        fake_drained_nodes.append(fake_associated_instance)
    shuffle(fake_drained_nodes)

    assert (
        len(fake_drained_nodes)
        == _NUM_DRAINED_NODES + _RATIO_HOT_BUFFER_TYPES * hot_buffer_total_count + _NUM_NODES_TERMINATING
    )
    (
        sorted_drained_nodes,
        sorted_buffer_drained_nodes,
        terminating_nodes,
    ) = sort_drained_nodes(app_settings, fake_drained_nodes)
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert len(sorted_drained_nodes) == (
        _NUM_DRAINED_NODES + _RATIO_HOT_BUFFER_TYPES * hot_buffer_total_count - hot_buffer_total_count
    )
    assert len(sorted_buffer_drained_nodes) == hot_buffer_total_count
    assert len(terminating_nodes) == _NUM_NODES_TERMINATING
    for n in terminating_nodes:
        assert n.node.spec
        assert n.node.spec.labels
        assert _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY in n.node.spec.labels


def test_sort_drained_nodes_inactivity_timeout(
    minimal_configuration: None,
    with_multiple_hot_buffer_instance_types: EnvVarsDict,
    app_settings: ApplicationSettings,
    random_fake_available_instances: list[EC2InstanceType],
    create_fake_node: Callable[..., DockerNode],
    create_associated_instance: Callable[..., AssociatedInstance],
    hot_buffer_instance_types: set[InstanceTypeType],
    hot_buffer_total_count: int,
):
    assert len(hot_buffer_instance_types) > 1, "this test needs at least 2 hot buffer instance types configured"
    assert app_settings.AUTOSCALING_EC2_INSTANCES

    selected_ec2_instance_type_with_inactivity_timeout = secrets.choice(tuple(hot_buffer_instance_types))

    ec2_config = app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
        selected_ec2_instance_type_with_inactivity_timeout
    ]
    ec2_config.hot_buffer_count = 2
    ec2_config.hot_buffer_max_inactivity_time = datetime.timedelta(seconds=5)

    old_node = create_fake_node()
    assert old_node.spec
    assert old_node.spec.labels is not None
    old_node.spec.labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=10)
    ).isoformat()

    fresh_node = create_fake_node()
    assert fresh_node.spec
    assert fresh_node.spec.labels is not None
    fresh_node.spec.labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = datetime.datetime.now(datetime.UTC).isoformat()

    drained_nodes = [
        create_associated_instance(
            old_node,
            terminateable_time=False,
            fake_ec2_instance_data_override={"type": selected_ec2_instance_type_with_inactivity_timeout},
        ),
        create_associated_instance(
            fresh_node,
            terminateable_time=False,
            fake_ec2_instance_data_override={"type": selected_ec2_instance_type_with_inactivity_timeout},
        ),
    ]

    other_drained_nodes, hot_buffer_drained_nodes, terminating_nodes = sort_drained_nodes(app_settings, drained_nodes)

    assert not terminating_nodes
    assert len(hot_buffer_drained_nodes) == 1
    assert len(other_drained_nodes) == 1
    assert hot_buffer_drained_nodes[0].node.description == fresh_node.description
