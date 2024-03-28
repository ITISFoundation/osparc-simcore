# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from aws_library.ec2.models import (
    AWSTagKey,
    AWSTagValue,
    EC2InstanceBootSpecific,
    EC2InstanceData,
)
from faker import Faker
from models_library.api_schemas_clusters_keeper.clusters import ClusterState
from models_library.clusters import (
    InternalClusterAuthentication,
    NoAuthentication,
    TLSAuthentication,
)
from pydantic import ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_clusters_keeper.core.settings import ApplicationSettings
from simcore_service_clusters_keeper.utils.clusters import (
    _prepare_environment_variables,
    create_cluster_from_ec2_instance,
    create_startup_script,
)
from types_aiobotocore_ec2.literals import InstanceStateNameType


@pytest.fixture
def cluster_machines_name_prefix(faker: Faker) -> str:
    return faker.pystr()


@pytest.fixture
def ec2_boot_specs(app_settings: ApplicationSettings) -> EC2InstanceBootSpecific:
    assert app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES
    ec2_boot_specs = next(
        iter(
            app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_ALLOWED_TYPES.values()
        )
    )
    assert isinstance(ec2_boot_specs, EC2InstanceBootSpecific)
    return ec2_boot_specs


def test_create_startup_script(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    app_settings: ApplicationSettings,
    cluster_machines_name_prefix: str,
    clusters_keeper_docker_compose: dict[str, Any],
    ec2_boot_specs: EC2InstanceBootSpecific,
):
    additional_custom_tags = {
        AWSTagKey("pytest-tag-key"): AWSTagValue("pytest-tag-value")
    }
    startup_script = create_startup_script(
        app_settings,
        cluster_machines_name_prefix=cluster_machines_name_prefix,
        ec2_boot_specific=ec2_boot_specs,
        additional_custom_tags=additional_custom_tags,
    )
    assert isinstance(startup_script, str)
    assert len(ec2_boot_specs.custom_boot_scripts) > 0
    for boot_script in ec2_boot_specs.custom_boot_scripts:
        assert boot_script in startup_script
    # we have commands to pipe into a docker-compose file
    assert " | base64 -d > /docker-compose.yml" in startup_script
    # we have commands to init a docker-swarm
    assert "docker swarm init" in startup_script
    # we have commands to deploy a stack
    assert (
        "docker stack deploy --with-registry-auth --compose-file=/docker-compose.yml dask_stack"
        in startup_script
    )
    # before that we have commands that setup ENV variables, let's check we have all of them as defined in the docker-compose
    # let's get what was set in the startup script and compare with the expected one of the docker-compose
    startup_script_envs_definition = (
        startup_script.splitlines()[-1].split("docker stack deploy")[0].strip()
    )
    assert startup_script_envs_definition
    # Use regular expression to split the string into key-value pairs (courtesy of chatGPT)
    startup_script_key_value_pairs: list[tuple[str, str]] = re.findall(
        r"(\S+)=([\S\s]+?)(?=\S+=|$)", startup_script_envs_definition
    )
    startup_script_env_keys_names = [key for key, _ in startup_script_key_value_pairs]
    # docker-compose expected values
    docker_compose_expected_environment: dict[str, str] = {}
    assert "services" in clusters_keeper_docker_compose
    assert isinstance(clusters_keeper_docker_compose["services"], dict)
    for service_details in clusters_keeper_docker_compose["services"].values():
        if "environment" in service_details:
            assert isinstance(service_details["environment"], dict)
            docker_compose_expected_environment |= service_details["environment"]

    # check the expected environment variables are set so the docker-compose will be complete (we define enough)
    expected_env_keys = [
        v[2:-1].split(":")[0]
        for v in docker_compose_expected_environment.values()
        if isinstance(v, str) and v.startswith("${")
    ] + ["DOCKER_IMAGE_TAG"]
    for env_key in expected_env_keys:
        assert (
            env_key in startup_script_env_keys_names
        ), f"{env_key} is missing from startup script! please adjust"

    # check we do not define "too much"
    for env_key in startup_script_env_keys_names:
        assert env_key in expected_env_keys

    # check lists have \" written in them
    list_settings = [
        "WORKERS_EC2_INSTANCES_SECURITY_GROUP_IDS",
    ]
    assert all(
        re.search(rf"{i}=\[(\\\".+\\\")*\]", startup_script) for i in list_settings
    )

    # check dicts have \' in front
    dict_settings = [
        "WORKERS_EC2_INSTANCES_ALLOWED_TYPES",
        "WORKERS_EC2_INSTANCES_CUSTOM_TAGS",
    ]
    assert all(
        re.search(rf"{i}=\'{{(\".+\":\s\".*\")+}}\'", startup_script)
        for i in dict_settings
    )

    # check the additional tags are in
    assert all(
        f'"{key}": "{value}"' in startup_script
        for key, value in additional_custom_tags.items()
    )


def test_create_startup_script_script_size_below_16kb(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    app_settings: ApplicationSettings,
    cluster_machines_name_prefix: str,
    clusters_keeper_docker_compose: dict[str, Any],
    ec2_boot_specs: EC2InstanceBootSpecific,
):
    additional_custom_tags = {
        AWSTagKey("pytest-tag-key"): AWSTagValue("pytest-tag-value")
    }
    startup_script = create_startup_script(
        app_settings,
        cluster_machines_name_prefix=cluster_machines_name_prefix,
        ec2_boot_specific=ec2_boot_specs,
        additional_custom_tags=additional_custom_tags,
    )
    script_size_in_bytes = len(startup_script.encode("utf-8"))

    print(
        f"current script size is {parse_obj_as(ByteSize, script_size_in_bytes).human_readable()}"
    )
    # NOTE: EC2 user data cannot be above 16KB, we keep some margin here
    assert script_size_in_bytes < 15 * 1024


def test_startup_script_defines_all_envs_for_docker_compose(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    app_settings: ApplicationSettings,
    cluster_machines_name_prefix: str,
    ec2_boot_specs: EC2InstanceBootSpecific,
    clusters_keeper_docker_compose_file: Path,
):
    additional_custom_tags = {
        AWSTagKey("pytest-tag-key"): AWSTagValue("pytest-tag-value")
    }
    environment_variables = _prepare_environment_variables(
        app_settings,
        cluster_machines_name_prefix=cluster_machines_name_prefix,
        additional_custom_tags=additional_custom_tags,
    )
    assert environment_variables
    process = subprocess.run(
        [  # noqa: S603, S607
            "docker",
            "compose",
            "--dry-run",
            f"--file={clusters_keeper_docker_compose_file}",
            "up",
        ],
        capture_output=True,
        check=True,
        env={
            e.split("=", maxsplit=1)[0]: e.split("=", maxsplit=1)[1]
            for e in environment_variables
        },
    )
    assert process
    assert process.stderr
    _ENV_VARIABLE_NOT_SET_ERROR = "variable is not set"
    assert _ENV_VARIABLE_NOT_SET_ERROR not in process.stderr.decode()
    assert process.stdout


@pytest.mark.parametrize(
    "ec2_state, expected_cluster_state",
    [
        ("pending", ClusterState.STARTED),
        ("running", ClusterState.RUNNING),
        ("shutting-down", ClusterState.STOPPED),
        ("stopped", ClusterState.STOPPED),
        ("stopping", ClusterState.STOPPED),
        ("terminated", ClusterState.STOPPED),
        ("whatever", ClusterState.STOPPED),
    ],
)
@pytest.mark.parametrize(
    "authentication",
    [
        NoAuthentication(),
        TLSAuthentication(**TLSAuthentication.Config.schema_extra["examples"][0]),
    ],
)
def test_create_cluster_from_ec2_instance(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    faker: Faker,
    ec2_state: InstanceStateNameType,
    expected_cluster_state: ClusterState,
    authentication: InternalClusterAuthentication,
):
    instance_data = fake_ec2_instance_data(state=ec2_state)
    cluster_instance = create_cluster_from_ec2_instance(
        instance_data,
        faker.pyint(),
        faker.pyint(),
        dask_scheduler_ready=faker.pybool(),
        cluster_auth=authentication,
    )
    assert cluster_instance
    assert cluster_instance.state is expected_cluster_state
    assert cluster_instance.authentication == authentication
