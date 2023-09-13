# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from typing import cast

import botocore.exceptions
import pytest
from faker import Faker
from fastapi import FastAPI
from moto.server import ThreadedMotoServer
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_clusters_keeper.core.errors import (
    ConfigurationError,
    Ec2InstanceNotFoundError,
    Ec2TooManyInstancesError,
)
from simcore_service_clusters_keeper.core.settings import (
    ApplicationSettings,
    EC2Settings,
)
from simcore_service_clusters_keeper.modules.ec2 import (
    ClustersKeeperEC2,
    EC2InstanceData,
    get_ec2_client,
)
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType


@pytest.fixture
def ec2_settings(
    app_environment: EnvVarsDict,
) -> EC2Settings:
    return EC2Settings.create_from_envs()


@pytest.fixture
def app_settings(
    app_environment: EnvVarsDict,
) -> ApplicationSettings:
    return ApplicationSettings.create_from_envs()


async def test_ec2_client_lifespan(ec2_settings: EC2Settings):
    ec2 = await ClustersKeeperEC2.create(settings=ec2_settings)
    assert ec2
    assert ec2.client
    assert ec2.exit_stack
    assert ec2.session

    await ec2.close()


async def test_ec2_client_raises_when_no_connection_available(ec2_client: EC2Client):
    with pytest.raises(
        botocore.exceptions.ClientError, match=r".+ AWS was not able to validate .+"
    ):
        await ec2_client.describe_account_attributes(DryRun=True)


async def test_ec2_client_with_mock_server(
    mocked_aws_server_envs: None, ec2_client: EC2Client
):
    # passes without exception
    await ec2_client.describe_account_attributes(DryRun=True)


async def test_ec2_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "ec2_client")
    assert initialized_app.state.ec2_client is None
    with pytest.raises(ConfigurationError):
        get_ec2_client(initialized_app)


async def test_ec2_client_when_ec2_server_goes_up_and_down(
    mocked_aws_server: ThreadedMotoServer,
    mocked_aws_server_envs: None,
    ec2_client: EC2Client,
):
    # passes without exception
    await ec2_client.describe_account_attributes(DryRun=True)
    mocked_aws_server.stop()
    with pytest.raises(botocore.exceptions.EndpointConnectionError):
        await ec2_client.describe_account_attributes(DryRun=True)

    # restart
    mocked_aws_server.start()
    # passes without exception
    await ec2_client.describe_account_attributes(DryRun=True)


async def test_ping(
    mocked_aws_server: ThreadedMotoServer,
    mocked_aws_server_envs: None,
    aws_allowed_ec2_instance_type_names: list[str],
    app_settings: ApplicationSettings,
    clusters_keeper_ec2: ClustersKeeperEC2,
):
    assert await clusters_keeper_ec2.ping() is True
    mocked_aws_server.stop()
    assert await clusters_keeper_ec2.ping() is False
    mocked_aws_server.start()
    assert await clusters_keeper_ec2.ping() is True


async def test_get_ec2_instance_capabilities(
    mocked_aws_server_envs: None,
    aws_allowed_ec2_instance_type_names: list[str],
    app_settings: ApplicationSettings,
    clusters_keeper_ec2: ClustersKeeperEC2,
):
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    instance_types = await clusters_keeper_ec2.get_ec2_instance_capabilities(
        cast(
            set[InstanceTypeType],
            set(app_settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES),
        )
    )
    assert instance_types
    assert len(instance_types) == len(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    )

    # all the instance names are found and valid
    assert all(
        i.name in app_settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
        for i in instance_types
    )
    for (
        instance_type_name
    ) in app_settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES:
        assert any(i.name == instance_type_name for i in instance_types)


async def test_start_aws_instance(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    clusters_keeper_ec2: ClustersKeeperEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
    mocker: MockerFixture,
):
    assert app_settings.CLUSTERS_KEEPER_EC2_ACCESS
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    instance_type = faker.pystr()
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    await clusters_keeper_ec2.start_aws_instance(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        instance_type,
        tags=tags,
        startup_script=startup_script,
        number_of_instances=1,
    )

    # check we have that now in ec2
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == 1
    running_instance = all_instances["Reservations"][0]
    assert "Instances" in running_instance
    assert len(running_instance["Instances"]) == 1
    running_instance = running_instance["Instances"][0]
    assert "InstanceType" in running_instance
    assert running_instance["InstanceType"] == instance_type
    assert "Tags" in running_instance
    assert running_instance["Tags"] == [
        {"Key": key, "Value": value} for key, value in tags.items()
    ]


async def test_start_aws_instance_is_limited_in_number_of_instances(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    clusters_keeper_ec2: ClustersKeeperEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
    mocker: MockerFixture,
):
    assert app_settings.CLUSTERS_KEEPER_EC2_ACCESS
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create as many instances as we can
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    for _ in range(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ):
        await clusters_keeper_ec2.start_aws_instance(
            app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
            faker.pystr(),
            tags=tags,
            startup_script=startup_script,
            number_of_instances=1,
        )

    # now creating one more shall fail
    with pytest.raises(Ec2TooManyInstancesError):
        await clusters_keeper_ec2.start_aws_instance(
            app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
            faker.pystr(),
            tags=tags,
            startup_script=startup_script,
            number_of_instances=1,
        )


async def test_get_instances(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    clusters_keeper_ec2: ClustersKeeperEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
    mocker: MockerFixture,
):
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    assert (
        await clusters_keeper_ec2.get_instances(
            app_settings.CLUSTERS_KEEPER_EC2_INSTANCES, tags={}
        )
        == []
    )

    # create some instance
    instance_type = faker.pystr()
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    created_instances = await clusters_keeper_ec2.start_aws_instance(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        instance_type,
        tags=tags,
        startup_script=startup_script,
        number_of_instances=1,
    )
    assert len(created_instances) == 1

    instance_received = await clusters_keeper_ec2.get_instances(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        tags=tags,
    )
    assert created_instances == instance_received


async def test_terminate_instance(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    clusters_keeper_ec2: ClustersKeeperEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
    mocker: MockerFixture,
):
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    # create some instance
    instance_type = faker.pystr()
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    created_instances = await clusters_keeper_ec2.start_aws_instance(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        instance_type,
        tags=tags,
        startup_script=startup_script,
        number_of_instances=1,
    )
    assert len(created_instances) == 1

    # terminate the instance
    await clusters_keeper_ec2.terminate_instances(created_instances)
    # calling it several times is ok, the instance stays a while
    await clusters_keeper_ec2.terminate_instances(created_instances)


async def test_terminate_instance_not_existing_raises(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    clusters_keeper_ec2: ClustersKeeperEC2,
    app_settings: ApplicationSettings,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    with pytest.raises(Ec2InstanceNotFoundError):
        await clusters_keeper_ec2.terminate_instances([fake_ec2_instance_data()])
