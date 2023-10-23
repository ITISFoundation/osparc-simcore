# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from collections.abc import Callable

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
):
    startup_script = create_startup_script(app_settings, cluster_machines_name_prefix)
    assert isinstance(startup_script, str)
    # we have commands to pipe into a docker-compose file
    assert " | base64 -d > docker-compose.yml" in startup_script
    # we have commands to init a docker-swarm
    assert "docker swarm init" in startup_script
    # we have commands that setup ENV variables
    assert app_settings.CLUSTERS_KEEPER_EC2_ACCESS
    ec2_access_environments = [
        f"EC2_ACCESS_KEY_ID={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.EC2_CLUSTERS_KEEPER_ACCESS_KEY_ID}",
        f"EC2_SECRET_ACCESS_KEY={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.EC2_CLUSTERS_KEEPER_SECRET_ACCESS_KEY}",
        f"EC2_REGION_NAME={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.EC2_CLUSTERS_KEEPER_REGION_NAME}",
        f"EC2_ENDPOINT={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.EC2_CLUSTERS_KEEPER_ENDPOINT}",
    ]
    assert all(i in startup_script for i in ec2_access_environments)

    ec2_instances_settings = [
        "EC2_INSTANCES_ALLOWED_TYPES",
        "EC2_INSTANCES_AMI_ID",
        "EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS",
        "EC2_INSTANCES_KEY_NAME",
        "EC2_INSTANCES_MAX_INSTANCES",
        "EC2_INSTANCES_NAME_PREFIX",
        "EC2_INSTANCES_SECURITY_GROUP_IDS",
        "EC2_INSTANCES_SUBNET_ID",
        f"EC2_INSTANCES_NAME_PREFIX={cluster_machines_name_prefix}",
    ]
    assert all(i in startup_script for i in ec2_instances_settings)

    # check lists have \" written in them
    list_settings = [
        "EC2_INSTANCES_ALLOWED_TYPES",
        "EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS",
        "EC2_INSTANCES_SECURITY_GROUP_IDS",
    ]
    assert all(
        re.search(rf"{i}=\[(\\\".+\\\")*\]", startup_script) for i in list_settings
    )

    # we have commands to deploy a stack
    assert (
        "docker stack deploy --with-registry-auth --compose-file=docker-compose.yml dask_stack"
        in startup_script
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
