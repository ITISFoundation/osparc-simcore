# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from collections.abc import AsyncIterator, Callable
from typing import cast, get_args

import botocore.exceptions
import pytest
from aws_library.ec2.client import SimcoreEC2API
from aws_library.ec2.errors import (
    EC2InstanceNotFoundError,
    EC2InstanceTypeInvalidError,
    EC2TooManyInstancesError,
)
from aws_library.ec2.models import (
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    EC2Tags,
)
from faker import Faker
from moto.server import ThreadedMotoServer
from settings_library.ec2 import EC2Settings
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType


def _ec2_allowed_types() -> list[InstanceTypeType]:
    return ["t2.nano", "m5.12xlarge", "g4dn.4xlarge"]


@pytest.fixture(scope="session")
def ec2_allowed_instances() -> list[InstanceTypeType]:
    return _ec2_allowed_types()


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


@pytest.fixture
def ec2_instance_config(
    fake_ec2_instance_type: EC2InstanceType,
    faker: Faker,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
) -> EC2InstanceConfig:
    return EC2InstanceConfig(
        type=fake_ec2_instance_type,
        tags=faker.pydict(allowed_types=(str,)),
        startup_script=faker.pystr(),
        ami_id=aws_ami_id,
        key_name=faker.pystr(),
        security_group_ids=[aws_security_group_id],
        subnet_id=aws_subnet_id,
        iam_instance_profile="",
    )


async def test_get_ec2_instance_capabilities(
    simcore_ec2_api: SimcoreEC2API,
    ec2_allowed_instances: list[InstanceTypeType],
):
    instance_types: list[
        EC2InstanceType
    ] = await simcore_ec2_api.get_ec2_instance_capabilities(
        cast(
            set[InstanceTypeType],
            set(ec2_allowed_instances),
        )
    )
    assert instance_types
    assert len(instance_types) == len(ec2_allowed_instances)

    # all the instance names are found and valid
    assert all(i.name in ec2_allowed_instances for i in instance_types)
    for instance_type_name in ec2_allowed_instances:
        assert any(i.name == instance_type_name for i in instance_types)


async def test_get_ec2_instance_capabilities_empty_list_returns_all_options(
    simcore_ec2_api: SimcoreEC2API,
):
    instance_types = await simcore_ec2_api.get_ec2_instance_capabilities(set())
    assert instance_types
    # NOTE: this might need adaptation when moto is updated
    assert 700 < len(instance_types) < 800


async def test_get_ec2_instance_capabilities_with_invalid_type_raises(
    simcore_ec2_api: SimcoreEC2API,
    faker: Faker,
):
    with pytest.raises(EC2InstanceTypeInvalidError):
        await simcore_ec2_api.get_ec2_instance_capabilities(set(faker.pystr()))


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
    expected_state: str,
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
            assert "State" in instance
            assert "Name" in instance["State"]
            assert instance["State"]["Name"] == expected_state


async def test_start_aws_instance(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    ec2_instance_config: EC2InstanceConfig,
):
    await _assert_no_instances_in_ec2(ec2_client)

    number_of_instances = 1

    # let's create a first reservation and check that it is correctly created in EC2
    await simcore_ec2_api.start_aws_instance(
        ec2_instance_config,
        min_number_of_instances=number_of_instances,
        number_of_instances=number_of_instances,
    )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=number_of_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )

    # create a second reservation
    await simcore_ec2_api.start_aws_instance(
        ec2_instance_config,
        min_number_of_instances=number_of_instances,
        number_of_instances=number_of_instances,
    )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=2,
        expected_num_instances=number_of_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )


@pytest.mark.parametrize("max_num_instances", [13])
async def test_start_aws_instance_is_limited_in_number_of_instances(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    ec2_instance_config: EC2InstanceConfig,
    max_num_instances: int,
):
    await _assert_no_instances_in_ec2(ec2_client)

    # create many instances in one go shall fail
    with pytest.raises(EC2TooManyInstancesError):
        await simcore_ec2_api.start_aws_instance(
            ec2_instance_config,
            min_number_of_instances=max_num_instances + 1,
            number_of_instances=max_num_instances + 1,
            max_total_number_of_instances=max_num_instances,
        )
    await _assert_no_instances_in_ec2(ec2_client)

    # create instances 1 by 1
    for _ in range(max_num_instances):
        await simcore_ec2_api.start_aws_instance(
            ec2_instance_config,
            min_number_of_instances=1,
            number_of_instances=1,
            max_total_number_of_instances=max_num_instances,
        )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=max_num_instances,
        expected_num_instances=1,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )

    # now creating one more shall fail
    with pytest.raises(EC2TooManyInstancesError):
        await simcore_ec2_api.start_aws_instance(
            ec2_instance_config,
            min_number_of_instances=1,
            number_of_instances=1,
            max_total_number_of_instances=max_num_instances,
        )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=max_num_instances,
        expected_num_instances=1,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )


async def test_get_instances(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    faker: Faker,
    ec2_instance_config: EC2InstanceConfig,
):
    # we have nothing running now in ec2
    await _assert_no_instances_in_ec2(ec2_client)
    assert (
        await simcore_ec2_api.get_instances(
            key_names=[ec2_instance_config.key_name], tags={}
        )
        == []
    )

    # create some instance
    _MAX_NUM_INSTANCES = 10
    num_instances = faker.pyint(min_value=1, max_value=_MAX_NUM_INSTANCES)
    created_instances = await simcore_ec2_api.start_aws_instance(
        ec2_instance_config,
        min_number_of_instances=num_instances,
        number_of_instances=num_instances,
    )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )
    # this returns all the entries using thes key names
    instance_received = await simcore_ec2_api.get_instances(
        key_names=[ec2_instance_config.key_name], tags={}
    )
    assert created_instances == instance_received

    # passing the tags will return the same
    instance_received = await simcore_ec2_api.get_instances(
        key_names=[ec2_instance_config.key_name], tags=ec2_instance_config.tags
    )
    assert created_instances == instance_received

    # asking for running state will also return the same
    instance_received = await simcore_ec2_api.get_instances(
        key_names=[ec2_instance_config.key_name],
        tags=ec2_instance_config.tags,
        state_names=["running"],
    )
    assert created_instances == instance_received

    # asking for other states shall return nothing
    for state in get_args(InstanceStateNameType):
        instance_received = await simcore_ec2_api.get_instances(
            key_names=[ec2_instance_config.key_name],
            tags=ec2_instance_config.tags,
            state_names=[state],
        )
        if state == "running":
            assert created_instances == instance_received
        else:
            assert not instance_received


async def test_terminate_instance(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    faker: Faker,
    ec2_instance_config: EC2InstanceConfig,
):
    # we have nothing running now in ec2
    await _assert_no_instances_in_ec2(ec2_client)
    # create some instance
    _NUM_INSTANCES = 10
    num_instances = faker.pyint(min_value=1, max_value=_NUM_INSTANCES)
    created_instances = await simcore_ec2_api.start_aws_instance(
        ec2_instance_config,
        min_number_of_instances=num_instances,
        number_of_instances=num_instances,
    )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )

    # terminate the instance
    await simcore_ec2_api.terminate_instances(created_instances)
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="terminated",
    )
    # calling it several times is ok, the instance stays a while
    await simcore_ec2_api.terminate_instances(created_instances)
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="terminated",
    )


async def test_terminate_instance_not_existing_raises(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    await _assert_no_instances_in_ec2(ec2_client)
    with pytest.raises(EC2InstanceNotFoundError):
        await simcore_ec2_api.terminate_instances([fake_ec2_instance_data()])


async def test_set_instance_tags(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    faker: Faker,
    ec2_instance_config: EC2InstanceConfig,
):
    await _assert_no_instances_in_ec2(ec2_client)
    # create some instance
    _MAX_NUM_INSTANCES = 10
    num_instances = faker.pyint(min_value=1, max_value=_MAX_NUM_INSTANCES)
    created_instances = await simcore_ec2_api.start_aws_instance(
        ec2_instance_config,
        min_number_of_instances=num_instances,
        number_of_instances=num_instances,
    )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )

    new_tags = faker.pydict(allowed_types=(str,))
    await simcore_ec2_api.set_instances_tags(created_instances, tags=new_tags)
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags | new_tags,
        expected_state="running",
    )


async def test_set_instance_tags_not_existing_raises(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    await _assert_no_instances_in_ec2(ec2_client)
    with pytest.raises(EC2InstanceNotFoundError):
        await simcore_ec2_api.set_instances_tags([fake_ec2_instance_data()], tags={})
