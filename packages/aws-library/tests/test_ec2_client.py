# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import datetime
import json
from collections.abc import AsyncIterator
from typing import cast

import botocore.exceptions
import pytest
from aws_library.ec2.client import SimcoreEC2API
from aws_library.ec2.errors import EC2TooManyInstancesError
from aws_library.ec2.models import EC2InstanceType, EC2Tags
from faker import Faker
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from settings_library.ec2 import EC2InstancesSettings, EC2Settings
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType


def _ec2_allowed_types() -> list[InstanceTypeType]:
    return ["t2.nano", "m5.12xlarge", "g4dn.4xlarge"]


@pytest.fixture(scope="session")
def ec2_allowed_instances() -> list[InstanceTypeType]:
    return _ec2_allowed_types()


@pytest.fixture
def client_environment(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    ec2_allowed_instances: list[InstanceTypeType],
) -> EnvVarsDict:
    # SEE https://faker.readthedocs.io/en/master/providers/faker.providers.internet.html?highlight=internet#faker-providers-internet
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_ACCESS_KEY_ID": faker.pystr(),
            "EC2_SECRET_ACCESS_KEY": faker.pystr(),
            "EC2_INSTANCES_KEY_NAME": faker.pystr(),
            "EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "EC2_INSTANCES_AMI_ID": faker.pystr(),
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(ec2_allowed_instances),
        },
    )
    return mock_env_devel_environment | envs


@pytest.fixture
def ec2_instances_settings(
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_allowed_instances: list[InstanceTypeType],
    faker: Faker,
) -> EC2InstancesSettings:
    return EC2InstancesSettings(
        EC2_INSTANCES_ALLOWED_TYPES=[f"{i}" for i in ec2_allowed_instances],
        EC2_INSTANCES_AMI_ID=aws_ami_id,
        EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS=faker.pylist(allowed_types=(str,)),
        EC2_INSTANCES_KEY_NAME=faker.pystr(),
        EC2_INSTANCES_MAX_INSTANCES=10,
        EC2_INSTANCES_NAME_PREFIX=faker.pystr(),
        EC2_INSTANCES_SECURITY_GROUP_IDS=[aws_security_group_id],
        EC2_INSTANCES_SUBNET_ID=aws_subnet_id,
        EC2_INSTANCES_TIME_BEFORE_TERMINATION=datetime.timedelta(seconds=10),
    )


@pytest.fixture
async def simcore_ec2_api(
    mocked_ec2_server_settings: EC2Settings,
) -> AsyncIterator[SimcoreEC2API]:
    ec2 = await SimcoreEC2API.create(settings=mocked_ec2_server_settings)
    assert ec2
    assert ec2.client
    assert ec2.exit_stack
    assert ec2.session
    yield ec2
    await ec2.close()


async def test_ec2_client_lifespan(simcore_ec2_api: SimcoreEC2API):
    ...


async def test_aiobotocore_ec2_client_when_ec2_server_goes_up_and_down(
    mocked_aws_server: ThreadedMotoServer,
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
    simcore_ec2_api: SimcoreEC2API,
):
    assert await simcore_ec2_api.ping() is True
    mocked_aws_server.stop()
    assert await simcore_ec2_api.ping() is False
    mocked_aws_server.start()
    assert await simcore_ec2_api.ping() is True


async def test_get_ec2_instance_capabilities(
    simcore_ec2_api: SimcoreEC2API,
    ec2_instances_settings: EC2InstancesSettings,
):
    instance_types: list[
        EC2InstanceType
    ] = await simcore_ec2_api.get_ec2_instance_capabilities(
        cast(
            set[InstanceTypeType],
            set(ec2_instances_settings.EC2_INSTANCES_ALLOWED_TYPES),
        )
    )
    assert instance_types
    assert len(instance_types) == len(
        ec2_instances_settings.EC2_INSTANCES_ALLOWED_TYPES
    )

    # all the instance names are found and valid
    assert all(
        i.name in ec2_instances_settings.EC2_INSTANCES_ALLOWED_TYPES
        for i in instance_types
    )
    for instance_type_name in ec2_instances_settings.EC2_INSTANCES_ALLOWED_TYPES:
        assert any(i.name == instance_type_name for i in instance_types)


@pytest.fixture(params=_ec2_allowed_types())
async def fake_ec2_instance_type(
    simcore_ec2_api: SimcoreEC2API,
    request: pytest.FixtureRequest,
) -> EC2InstanceType:
    instance_type_name: InstanceTypeType = request.param
    instance_types: list[
        EC2InstanceType
    ] = await simcore_ec2_api.get_ec2_instance_capabilities({instance_type_name})

    assert len(instance_types) == 1
    return instance_types[0]


async def _assert_no_instances_in_ec2(ec2_client: EC2Client) -> None:
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]


async def _assert_instances_in_ec2(
    ec2_client: EC2Client,
    *,
    expected_num_reservations: int,
    expected_num_instances: int,
    expected_instance_type: EC2InstanceType,
    expected_tags: EC2Tags,
) -> None:
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == expected_num_reservations
    for reservation in all_instances["Reservations"]:
        assert "Instances" in reservation
        assert len(reservation["Instances"]) == expected_num_instances
        for instance in reservation["Instances"]:
            assert "InstanceType" in instance
            assert instance["InstanceType"] == expected_instance_type.name
            assert "Tags" in instance
            assert instance["Tags"] == [
                {"Key": key, "Value": value} for key, value in expected_tags.items()
            ]


async def test_start_aws_instance(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    faker: Faker,
    fake_ec2_instance_type: EC2InstanceType,
    ec2_instances_settings: EC2InstancesSettings,
):
    await _assert_no_instances_in_ec2(ec2_client)

    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    number_of_instances = 1

    # let's create a first reservation and check that it is correctly created in EC2
    await simcore_ec2_api.start_aws_instance(
        ec2_instances_settings,
        fake_ec2_instance_type,
        tags=tags,
        startup_script=startup_script,
        number_of_instances=number_of_instances,
    )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=number_of_instances,
        expected_instance_type=fake_ec2_instance_type,
        expected_tags=tags,
    )

    # create a second reservation
    await simcore_ec2_api.start_aws_instance(
        ec2_instances_settings,
        fake_ec2_instance_type,
        tags=tags,
        startup_script=startup_script,
        number_of_instances=number_of_instances,
    )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=2,
        expected_num_instances=number_of_instances,
        expected_instance_type=fake_ec2_instance_type,
        expected_tags=tags,
    )


async def test_start_aws_instance_is_limited_in_number_of_instances(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    faker: Faker,
    fake_ec2_instance_type: EC2InstanceType,
    ec2_instances_settings: EC2InstancesSettings,
):
    await _assert_no_instances_in_ec2(ec2_client)

    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()

    # create many instances in one go shall fail
    with pytest.raises(EC2TooManyInstancesError):
        await simcore_ec2_api.start_aws_instance(
            ec2_instances_settings,
            fake_ec2_instance_type,
            tags=tags,
            startup_script=startup_script,
            number_of_instances=ec2_instances_settings.EC2_INSTANCES_MAX_INSTANCES + 1,
        )
    await _assert_no_instances_in_ec2(ec2_client)

    # create instances 1 by 1
    for _ in range(ec2_instances_settings.EC2_INSTANCES_MAX_INSTANCES):
        await simcore_ec2_api.start_aws_instance(
            ec2_instances_settings,
            fake_ec2_instance_type,
            tags=tags,
            startup_script=startup_script,
            number_of_instances=1,
        )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=ec2_instances_settings.EC2_INSTANCES_MAX_INSTANCES,
        expected_num_instances=1,
        expected_instance_type=fake_ec2_instance_type,
        expected_tags=tags,
    )

    # now creating one more shall fail
    with pytest.raises(EC2TooManyInstancesError):
        await simcore_ec2_api.start_aws_instance(
            ec2_instances_settings,
            fake_ec2_instance_type,
            tags=tags,
            startup_script=startup_script,
            number_of_instances=1,
        )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=ec2_instances_settings.EC2_INSTANCES_MAX_INSTANCES,
        expected_num_instances=1,
        expected_instance_type=fake_ec2_instance_type,
        expected_tags=tags,
    )


# async def test_get_instances(
#     mocked_ec2_server_envs: None,
#     aws_vpc_id: str,
#     aws_subnet_id: str,
#     aws_security_group_id: str,
#     aws_ami_id: str,
#     ec2_client: EC2Client,
#     autoscaling_ec2: AutoscalingEC2,
#     app_settings: ApplicationSettings,
#     faker: Faker,
#     fake_ec2_instance_type: EC2InstanceType,
# ):
#     assert app_settings.AUTOSCALING_EC2_INSTANCES
#     # we have nothing running now in ec2
#     all_instances = await ec2_client.describe_instances()
#     assert not all_instances["Reservations"]
#     assert (
#         await autoscaling_ec2.get_instances(app_settings.AUTOSCALING_EC2_INSTANCES, {})
#         == []
#     )

#     # create some instance
#     tags = faker.pydict(allowed_types=(str,))
#     startup_script = faker.pystr()
#     created_instances = await autoscaling_ec2.start_aws_instance(
#         app_settings.AUTOSCALING_EC2_INSTANCES,
#         fake_ec2_instance_type,
#         tags=tags,
#         startup_script=startup_script,
#         number_of_instances=1,
#     )
#     assert len(created_instances) == 1

#     instance_received = await autoscaling_ec2.get_instances(
#         app_settings.AUTOSCALING_EC2_INSTANCES,
#         tags=tags,
#     )
#     assert created_instances == instance_received


# async def test_terminate_instance(
#     mocked_ec2_server_envs: None,
#     aws_vpc_id: str,
#     aws_subnet_id: str,
#     aws_security_group_id: str,
#     aws_ami_id: str,
#     ec2_client: EC2Client,
#     autoscaling_ec2: AutoscalingEC2,
#     app_settings: ApplicationSettings,
#     faker: Faker,
#     fake_ec2_instance_type: EC2InstanceType,
# ):
#     assert app_settings.AUTOSCALING_EC2_INSTANCES
#     # we have nothing running now in ec2
#     all_instances = await ec2_client.describe_instances()
#     assert not all_instances["Reservations"]
#     # create some instance
#     tags = faker.pydict(allowed_types=(str,))
#     startup_script = faker.pystr()
#     created_instances = await autoscaling_ec2.start_aws_instance(
#         app_settings.AUTOSCALING_EC2_INSTANCES,
#         fake_ec2_instance_type,
#         tags=tags,
#         startup_script=startup_script,
#         number_of_instances=1,
#     )
#     assert len(created_instances) == 1

#     # terminate the instance
#     await autoscaling_ec2.terminate_instances(created_instances)
#     # calling it several times is ok, the instance stays a while
#     await autoscaling_ec2.terminate_instances(created_instances)


# async def test_terminate_instance_not_existing_raises(
#     mocked_ec2_server_envs: None,
#     aws_vpc_id: str,
#     aws_subnet_id: str,
#     aws_security_group_id: str,
#     aws_ami_id: str,
#     ec2_client: EC2Client,
#     autoscaling_ec2: AutoscalingEC2,
#     app_settings: ApplicationSettings,
#     fake_ec2_instance_data: Callable[..., EC2InstanceData],
# ):
#     assert app_settings.AUTOSCALING_EC2_INSTANCES
#     # we have nothing running now in ec2
#     all_instances = await ec2_client.describe_instances()
#     assert not all_instances["Reservations"]
#     with pytest.raises(Ec2InstanceNotFoundError):
#         await autoscaling_ec2.terminate_instances([fake_ec2_instance_data()])
