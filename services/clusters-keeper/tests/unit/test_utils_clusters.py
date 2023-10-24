# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from collections.abc import Callable
from typing import Any

import pytest
from faker import Faker
from models_library.rpc_schemas_clusters_keeper.clusters import ClusterState
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_clusters_keeper.core.settings import ApplicationSettings
from simcore_service_clusters_keeper.models import EC2InstanceData
from simcore_service_clusters_keeper.utils.clusters import (
    create_cluster_from_ec2_instance,
    create_startup_script,
)
from types_aiobotocore_ec2.literals import InstanceStateNameType


@pytest.fixture
def cluster_machines_name_prefix(faker: Faker) -> str:
    return faker.pystr()


def test_create_startup_script(
    disabled_rabbitmq: None,
    mocked_aws_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    app_settings: ApplicationSettings,
    cluster_machines_name_prefix: str,
    clusters_keeper_docker_compose: dict[str, Any],
):
    startup_script = create_startup_script(app_settings, cluster_machines_name_prefix)
    assert isinstance(startup_script, str)
    # we have commands to pipe into a docker-compose file
    assert " | base64 -d > docker-compose.yml" in startup_script
    # we have commands to init a docker-swarm
    assert "docker swarm init" in startup_script
    # we have commands to deploy a stack
    assert (
        "docker stack deploy --with-registry-auth --compose-file=docker-compose.yml dask_stack"
        in startup_script
    )
    # before that we have commands that setup ENV variables, let's check we have all of them as defined in the docker-compose
    # let's get what was set in the startup script and compare with the expected one of the docker-compose
    startup_script_envs_definition = (
        startup_script.splitlines()[-1].split("docker stack deploy")[0].strip()
    )
    assert startup_script_envs_definition
    startup_script_env_keys_names = {
        entry.split("=", maxsplit=1)[0]: entry.split("=", maxsplit=1)[1]
        for entry in startup_script_envs_definition.split(" ")
    }
    # docker-compose expected values
    assert "services" in clusters_keeper_docker_compose
    assert "autoscaling" in clusters_keeper_docker_compose["services"]
    assert "environment" in clusters_keeper_docker_compose["services"]["autoscaling"]
    docker_compose_expected_environment: dict[
        str, str
    ] = clusters_keeper_docker_compose["services"]["autoscaling"]["environment"]
    assert isinstance(docker_compose_expected_environment, dict)

    # check the expected environment variables are set so the docker-compose will be complete (we define enough)
    expected_env_keys = [
        v[2:-1].split(":")[0]
        for v in docker_compose_expected_environment.values()
        if isinstance(v, str) and v.startswith("${")
    ] + ["DOCKER_IMAGE_TAG"]
    for env_key in expected_env_keys:
        assert env_key in startup_script_env_keys_names

    # check we do not define "too much"
    for env_key in startup_script_env_keys_names:
        assert env_key in expected_env_keys

    # check lists have \" written in them
    list_settings = [
        "WORKERS_EC2_INSTANCES_ALLOWED_TYPES",
        "WORKERS_EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS",
        "WORKERS_EC2_INSTANCES_SECURITY_GROUP_IDS",
    ]
    assert all(
        re.search(rf"{i}=\[(\\\".+\\\")*\]", startup_script) for i in list_settings
    )


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
def test_create_cluster_from_ec2_instance(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    faker: Faker,
    ec2_state: InstanceStateNameType,
    expected_cluster_state: ClusterState,
):
    instance_data = fake_ec2_instance_data(state=ec2_state)
    cluster_instance = create_cluster_from_ec2_instance(
        instance_data,
        faker.pyint(),
        faker.pyint(),
        dask_scheduler_ready=faker.pybool(),
    )
    assert cluster_instance
    assert cluster_instance.state is expected_cluster_state
