# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import datetime
import json
import re
from collections.abc import Callable
from random import choice, shuffle

import arrow
import pytest
from aws_library.ec2 import EC2InstanceType
from faker import Faker
from models_library.docker import DockerGenericTag
from models_library.generated_models.docker_rest_api import Node as DockerNode
from pydantic import parse_obj_as
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_autoscaling.core.errors import Ec2InvalidDnsNameError
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import AssociatedInstance, EC2InstanceData
from simcore_service_autoscaling.utils.auto_scaling_core import (
    associate_ec2_instances_with_nodes,
    ec2_startup_script,
    get_machine_buffer_type,
    node_host_name_from_ec2_private_dns,
    sort_drained_nodes,
)
from simcore_service_autoscaling.utils.utils_docker import (
    _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY,
)


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


@pytest.mark.parametrize(
    "aws_private_dns, expected_host_name",
    [
        ("ip-10-12-32-3.internal-data", "ip-10-12-32-3"),
        ("ip-10-12-32-32.internal-data", "ip-10-12-32-32"),
        ("ip-10-0-3-129.internal-data", "ip-10-0-3-129"),
        ("ip-10-0-3-12.internal-data", "ip-10-0-3-12"),
    ],
)
def test_node_host_name_from_ec2_private_dns(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    aws_private_dns: str,
    expected_host_name: str,
):
    instance = fake_ec2_instance_data(
        aws_private_dns=aws_private_dns,
    )
    assert node_host_name_from_ec2_private_dns(instance) == expected_host_name


def test_node_host_name_from_ec2_private_dns_raises_with_invalid_name(
    fake_ec2_instance_data: Callable[..., EC2InstanceData], faker: Faker
):
    instance = fake_ec2_instance_data(aws_private_dns=faker.name())
    with pytest.raises(Ec2InvalidDnsNameError):
        node_host_name_from_ec2_private_dns(instance)


@pytest.mark.parametrize("valid_ec2_dns", [True, False])
async def test_associate_ec2_instances_with_nodes_with_no_correspondence(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., DockerNode],
    valid_ec2_dns: bool,
):
    nodes = [node() for _ in range(10)]
    ec2_instances = [
        (
            fake_ec2_instance_data(aws_private_dns=f"ip-10-12-32-{n+1}.internal-data")
            if valid_ec2_dns
            else fake_ec2_instance_data()
        )
        for n in range(10)
    ]

    (
        associated_instances,
        non_associated_instances,
    ) = await associate_ec2_instances_with_nodes(nodes, ec2_instances)

    assert not associated_instances
    assert non_associated_instances
    assert len(non_associated_instances) == len(ec2_instances)


async def test_associate_ec2_instances_with_corresponding_nodes(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., DockerNode],
):
    nodes = []
    ec2_instances = []
    for n in range(10):
        host_name = f"ip-10-12-32-{n+1}"
        nodes.append(node(Description={"Hostname": host_name}))
        ec2_instances.append(
            fake_ec2_instance_data(aws_private_dns=f"{host_name}.internal-data")
        )

    (
        associated_instances,
        non_associated_instances,
    ) = await associate_ec2_instances_with_nodes(nodes, ec2_instances)

    assert associated_instances
    assert not non_associated_instances
    assert len(associated_instances) == len(ec2_instances)
    assert len(associated_instances) == len(nodes)
    for associated_instance in associated_instances:
        assert associated_instance.node.Description
        assert associated_instance.node.Description.Hostname
        assert (
            associated_instance.node.Description.Hostname
            in associated_instance.ec2_instance.aws_private_dns
        )


@pytest.fixture
def minimal_configuration(
    docker_swarm: None,
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    disable_dynamic_service_background_task: None,
    mocked_redis_server: None,
) -> None:
    ...


@pytest.fixture
def ec2_instances_boot_just_ami(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, faker: Faker
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {"t2.micro": {"ami_id": faker.pystr()}}
            ),
        },
    )
    return app_environment | envs


async def test_ec2_startup_script_just_ami(
    minimal_configuration: None,
    ec2_instances_boot_just_ami: EnvVarsDict,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_boot_specific = next(
        iter(
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()
        )
    )
    assert not instance_boot_specific.pre_pull_images
    assert instance_boot_specific.pre_pull_images_cron_interval == datetime.timedelta(
        minutes=30
    )
    startup_script = await ec2_startup_script(instance_boot_specific, app_settings)
    assert len(startup_script.split("&&")) == 1
    assert re.fullmatch(
        r"^docker swarm join --availability=drain --token .*$", startup_script
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
    images = parse_obj_as(
        list[DockerGenericTag],
        [
            "nginx:latest",
            "itisfoundation/my-very-nice-service:latest",
            "simcore/services/dynamic/another-nice-one:2.4.5",
            "asd",
        ],
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


async def test_ec2_startup_script_with_pre_pulling(
    minimal_configuration: None,
    ec2_instances_boot_ami_pre_pull: EnvVarsDict,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_boot_specific = next(
        iter(
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()
        )
    )
    assert instance_boot_specific.pre_pull_images
    assert instance_boot_specific.pre_pull_images_cron_interval
    startup_script = await ec2_startup_script(instance_boot_specific, app_settings)
    assert len(startup_script.split("&&")) == 7
    assert re.fullmatch(
        r"^(docker swarm join [^&&]+) && (echo [^\s]+ \| docker login [^&&]+) && (echo [^&&]+) && (echo [^&&]+) && (chmod \+x [^&&]+) && (./docker-pull-script.sh) && (echo .+)$",
        startup_script,
    ), f"{startup_script=}"


async def test_ec2_startup_script_with_custom_scripts(
    minimal_configuration: None,
    ec2_instances_boot_ami_scripts: list[str],
    app_settings: ApplicationSettings,
):
    for _ in range(3):
        assert app_settings.AUTOSCALING_EC2_INSTANCES
        instance_boot_specific = next(
            iter(
                app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()
            )
        )
        assert not instance_boot_specific.pre_pull_images
        assert instance_boot_specific.pre_pull_images_cron_interval
        startup_script = await ec2_startup_script(instance_boot_specific, app_settings)
        assert len(startup_script.split("&&")) == 1 + len(
            ec2_instances_boot_ami_scripts
        )
        assert re.fullmatch(
            rf"^([^&&]+ &&){{{len(ec2_instances_boot_ami_scripts)}}} (docker swarm join .+)$",
            startup_script,
        ), f"{startup_script=}"


async def test_ec2_startup_script_with_pre_pulling_but_no_registry(
    minimal_configuration: None,
    ec2_instances_boot_ami_pre_pull: EnvVarsDict,
    disabled_registry: None,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_boot_specific = next(
        iter(
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.values()
        )
    )
    assert instance_boot_specific.pre_pull_images
    assert instance_boot_specific.pre_pull_images_cron_interval
    startup_script = await ec2_startup_script(instance_boot_specific, app_settings)
    assert len(startup_script.split("&&")) == 1
    assert re.fullmatch(
        r"^docker swarm join --availability=drain --token .*$", startup_script
    )


def test_get_machine_buffer_type(
    random_fake_available_instances: list[EC2InstanceType],
):
    assert (
        get_machine_buffer_type(random_fake_available_instances)
        == random_fake_available_instances[0]
    )


def test_sort_empty_drained_nodes(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    random_fake_available_instances: list[EC2InstanceType],
):
    assert sort_drained_nodes(app_settings, [], random_fake_available_instances) == (
        [],
        [],
        [],
    )


def test_sort_drained_nodes(
    mock_machines_buffer: int,
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    random_fake_available_instances: list[EC2InstanceType],
    create_fake_node: Callable[..., DockerNode],
    create_associated_instance: Callable[..., AssociatedInstance],
):
    machine_buffer_type = get_machine_buffer_type(random_fake_available_instances)
    _NUM_DRAINED_NODES = 20
    _NUM_NODE_WITH_TYPE_BUFFER = 3 * mock_machines_buffer
    _NUM_NODES_TERMINATING = 13
    fake_drained_nodes = []
    for _ in range(_NUM_DRAINED_NODES):
        fake_node = create_fake_node()
        fake_associated_instance = create_associated_instance(
            fake_node,
            terminateable_time=False,
            fake_ec2_instance_data_override={
                "type": choice(  # noqa: S311
                    [
                        i
                        for i in random_fake_available_instances
                        if i != machine_buffer_type
                    ]
                ).name
            },
        )
        fake_drained_nodes.append(fake_associated_instance)

    for _ in range(_NUM_NODE_WITH_TYPE_BUFFER):
        fake_node = create_fake_node()
        fake_associated_instance = create_associated_instance(
            fake_node,
            terminateable_time=False,
            fake_ec2_instance_data_override={"type": machine_buffer_type.name},
        )
        fake_drained_nodes.append(fake_associated_instance)

    for _ in range(_NUM_NODES_TERMINATING):
        fake_node = create_fake_node()
        assert fake_node.Spec
        assert fake_node.Spec.Labels
        fake_node.Spec.Labels[
            _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY
        ] = arrow.utcnow().datetime.isoformat()
        fake_associated_instance = create_associated_instance(
            fake_node,
            terminateable_time=False,
            fake_ec2_instance_data_override={"type": machine_buffer_type.name},
        )
        fake_drained_nodes.append(fake_associated_instance)
    shuffle(fake_drained_nodes)

    assert (
        len(fake_drained_nodes)
        == _NUM_DRAINED_NODES + _NUM_NODE_WITH_TYPE_BUFFER + _NUM_NODES_TERMINATING
    )
    (
        sorted_drained_nodes,
        sorted_buffer_drained_nodes,
        terminating_nodes,
    ) = sort_drained_nodes(
        app_settings, fake_drained_nodes, random_fake_available_instances
    )
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        mock_machines_buffer
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    )
    assert len(sorted_drained_nodes) == (
        _NUM_DRAINED_NODES
        + _NUM_NODE_WITH_TYPE_BUFFER
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    )
    assert (
        len(sorted_buffer_drained_nodes)
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    )
    assert len(terminating_nodes) == _NUM_NODES_TERMINATING
    for n in terminating_nodes:
        assert n.node.Spec
        assert n.node.Spec.Labels
        assert _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY in n.node.Spec.Labels
