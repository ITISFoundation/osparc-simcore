# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import botocore.exceptions
import pytest
from faker import Faker
from fastapi import FastAPI
from moto.server import ThreadedMotoServer
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.errors import (
    ConfigurationError,
    Ec2InstanceNotFoundError,
    Ec2TooManyInstancesError,
)
from simcore_service_autoscaling.core.settings import ApplicationSettings, EC2Settings
from simcore_service_autoscaling.modules.ec2 import (
    AutoscalingEC2,
    EC2InstanceData,
    get_ec2_client,
)
from types_aiobotocore_ec2 import EC2Client


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
    ec2 = await AutoscalingEC2.create(settings=ec2_settings)
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
    assert initialized_app.state.ec2_client == None
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
    autoscaling_ec2: AutoscalingEC2,
):
    assert await autoscaling_ec2.ping() is True
    mocked_aws_server.stop()
    assert await autoscaling_ec2.ping() is False
    mocked_aws_server.start()
    assert await autoscaling_ec2.ping() is True


async def test_get_ec2_instance_capabilities(
    mocked_aws_server_envs: None,
    aws_allowed_ec2_instance_type_names: list[str],
    app_settings: ApplicationSettings,
    autoscaling_ec2: AutoscalingEC2,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_types = await autoscaling_ec2.get_ec2_instance_capabilities(
        app_settings.AUTOSCALING_EC2_INSTANCES
    )
    assert instance_types
    assert len(instance_types) == len(
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    )

    # all the instance names are found and valid
    assert all(
        i.name in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
        for i in instance_types
    )
    for (
        instance_type_name
    ) in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES:
        assert any(i.name == instance_type_name for i in instance_types)


async def test_start_aws_instance(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    autoscaling_ec2: AutoscalingEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
    mocker: MockerFixture,
):
    assert app_settings.AUTOSCALING_EC2_ACCESS
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    instance_type = faker.pystr()
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    progress_mock_fct = mocker.AsyncMock()
    await autoscaling_ec2.start_aws_instance(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        instance_type,
        tags=tags,
        startup_script=startup_script,
        number_of_instances=1,
        progress_callback=progress_mock_fct,
    )
    assert progress_mock_fct.call_count == 3

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
    autoscaling_ec2: AutoscalingEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
    mocker: MockerFixture,
):
    assert app_settings.AUTOSCALING_EC2_ACCESS
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create as many instances as we can
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    progress_mock_fct = mocker.AsyncMock()
    for _ in range(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES):
        await autoscaling_ec2.start_aws_instance(
            app_settings.AUTOSCALING_EC2_INSTANCES,
            faker.pystr(),
            tags=tags,
            startup_script=startup_script,
            number_of_instances=1,
            progress_callback=progress_mock_fct,
        )

    # now creating one more shall fail
    with pytest.raises(Ec2TooManyInstancesError):
        await autoscaling_ec2.start_aws_instance(
            app_settings.AUTOSCALING_EC2_INSTANCES,
            faker.pystr(),
            tags=tags,
            startup_script=startup_script,
            number_of_instances=1,
            progress_callback=progress_mock_fct,
        )


async def test_get_running_instance_raises_if_not_found(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    autoscaling_ec2: AutoscalingEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    with pytest.raises(Ec2InstanceNotFoundError):
        await autoscaling_ec2.get_running_instance(
            app_settings.AUTOSCALING_EC2_INSTANCES,
            tag_keys=[],
            instance_host_name=faker.pystr(),
        )


async def test_get_running_instance(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    autoscaling_ec2: AutoscalingEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
    mocker: MockerFixture,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create some instance
    instance_type = faker.pystr()
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    progress_mock_fct = mocker.AsyncMock()
    created_instances = await autoscaling_ec2.start_aws_instance(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        instance_type,
        tags=tags,
        startup_script=startup_script,
        number_of_instances=1,
        progress_callback=progress_mock_fct,
    )
    assert len(created_instances) == 1

    instance_received = await autoscaling_ec2.get_running_instance(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        tag_keys=list(tags.keys()),
        instance_host_name=created_instances[0].aws_private_dns.split(".ec2.internal")[
            0
        ],
    )
    assert created_instances[0] == instance_received


async def test_terminate_instance(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    autoscaling_ec2: AutoscalingEC2,
    app_settings: ApplicationSettings,
    faker: Faker,
    mocker: MockerFixture,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    # create some instance
    instance_type = faker.pystr()
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    progress_mock_fct = mocker.AsyncMock()
    created_instances = await autoscaling_ec2.start_aws_instance(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        instance_type,
        tags=tags,
        startup_script=startup_script,
        number_of_instances=1,
        progress_callback=progress_mock_fct,
    )
    assert len(created_instances) == 1

    # terminate the instance
    await autoscaling_ec2.terminate_instance(created_instances[0])
    # calling it several times is ok, the instance stays a while
    await autoscaling_ec2.terminate_instance(created_instances[0])


async def test_terminate_instance_not_existing_raises(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    autoscaling_ec2: AutoscalingEC2,
    app_settings: ApplicationSettings,
    ec2_instance_data: EC2InstanceData,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    with pytest.raises(Ec2InstanceNotFoundError):
        await autoscaling_ec2.terminate_instance(ec2_instance_data)
