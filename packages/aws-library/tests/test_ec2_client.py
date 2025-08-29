# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import random
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import fields
from typing import Any, cast, get_args

import botocore.exceptions
import pytest
from aws_library.ec2._client import SimcoreEC2API
from aws_library.ec2._errors import (
    EC2InstanceNotFoundError,
    EC2InstanceTypeInvalidError,
    EC2InsufficientCapacityError,
    EC2TooManyInstancesError,
)
from aws_library.ec2._models import (
    AWSTagKey,
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    EC2Tags,
)
from faker import Faker
from moto.server import ThreadedMotoServer
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from settings_library.ec2 import EC2Settings
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType


def _ec2_allowed_types() -> list[InstanceTypeType]:
    return ["m5.12xlarge"]


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


async def test_ec2_client_lifespan(simcore_ec2_api: SimcoreEC2API): ...


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
        subnet_ids=[aws_subnet_id],
        iam_instance_profile="",
    )


async def test_get_ec2_instance_capabilities(
    simcore_ec2_api: SimcoreEC2API,
    ec2_allowed_instances: list[InstanceTypeType],
):
    instance_types: list[EC2InstanceType] = (
        await simcore_ec2_api.get_ec2_instance_capabilities(
            cast(
                set[InstanceTypeType],
                set(ec2_allowed_instances),
            )
        )
    )
    assert instance_types
    assert [_.name for _ in instance_types] == sorted(ec2_allowed_instances)


async def test_get_ec2_instance_capabilities_returns_all_options(
    simcore_ec2_api: SimcoreEC2API,
):
    instance_types = await simcore_ec2_api.get_ec2_instance_capabilities("ALL")
    assert instance_types
    # NOTE: this might need adaptation when moto is updated
    assert (
        850 < len(instance_types) < 877
    ), f"received {len(instance_types)}, the test might need adaptation"


async def test_get_ec2_instance_capabilities_raise_with_empty_set(
    simcore_ec2_api: SimcoreEC2API,
):
    with pytest.raises(ValueError, match="instance_type_names"):
        await simcore_ec2_api.get_ec2_instance_capabilities(set())


async def test_get_ec2_instance_capabilities_with_invalid_type_raises(
    simcore_ec2_api: SimcoreEC2API,
    faker: Faker,
):
    with pytest.raises(EC2InstanceTypeInvalidError):
        await simcore_ec2_api.get_ec2_instance_capabilities(
            faker.pyset(allowed_types=(str,))
        )


@pytest.fixture(params=_ec2_allowed_types())
async def fake_ec2_instance_type(
    simcore_ec2_api: SimcoreEC2API,
    request: pytest.FixtureRequest,
) -> EC2InstanceType:
    instance_type_name: InstanceTypeType = request.param
    instance_types: list[EC2InstanceType] = (
        await simcore_ec2_api.get_ec2_instance_capabilities({instance_type_name})
    )

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


async def test_launch_instances(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    ec2_instance_config: EC2InstanceConfig,
):
    await _assert_no_instances_in_ec2(ec2_client)

    number_of_instances = 1

    # let's create a first reservation and check that it is correctly created in EC2
    await simcore_ec2_api.launch_instances(
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
    await simcore_ec2_api.launch_instances(
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
async def test_launch_instances_is_limited_in_number_of_instances(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    ec2_instance_config: EC2InstanceConfig,
    max_num_instances: int,
):
    await _assert_no_instances_in_ec2(ec2_client)

    # create many instances in one go shall fail
    with pytest.raises(EC2TooManyInstancesError):
        await simcore_ec2_api.launch_instances(
            ec2_instance_config,
            min_number_of_instances=max_num_instances + 1,
            number_of_instances=max_num_instances + 1,
            max_total_number_of_instances=max_num_instances,
        )
    await _assert_no_instances_in_ec2(ec2_client)

    # create instances 1 by 1
    for _ in range(max_num_instances):
        await simcore_ec2_api.launch_instances(
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
        await simcore_ec2_api.launch_instances(
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
    created_instances = await simcore_ec2_api.launch_instances(
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


async def test_stop_start_instances(
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
    created_instances = await simcore_ec2_api.launch_instances(
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
    # stop the instances
    await simcore_ec2_api.stop_instances(created_instances)
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="stopped",
    )

    # stop again is ok
    await simcore_ec2_api.stop_instances(created_instances)
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="stopped",
    )

    # start the instances now
    started_instances = await simcore_ec2_api.start_instances(created_instances)
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )
    # the public IPs change when the instances are stopped and started
    for s, c in zip(started_instances, created_instances, strict=True):
        # the rest shall be the same
        for f in fields(EC2InstanceData):
            if f.name == "aws_public_ip":
                assert getattr(s, f.name) != getattr(c, f.name)
            else:
                assert getattr(s, f.name) == getattr(c, f.name)


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
    created_instances = await simcore_ec2_api.launch_instances(
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


async def test_start_instance_not_existing_raises(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    await _assert_no_instances_in_ec2(ec2_client)
    with pytest.raises(EC2InstanceNotFoundError):
        await simcore_ec2_api.start_instances([fake_ec2_instance_data()])


async def test_stop_instance_not_existing_raises(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    await _assert_no_instances_in_ec2(ec2_client)
    with pytest.raises(EC2InstanceNotFoundError):
        await simcore_ec2_api.stop_instances([fake_ec2_instance_data()])


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
    created_instances = await simcore_ec2_api.launch_instances(
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

    # now remove some, this should do nothing
    await simcore_ec2_api.remove_instances_tags(
        created_instances,
        tag_keys=[TypeAdapter(AWSTagKey).validate_python("whatever_i_dont_exist")],
    )
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_instances,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags | new_tags,
        expected_state="running",
    )
    # now remove some real ones
    tag_key_to_remove = random.choice(list(new_tags))  # noqa: S311
    await simcore_ec2_api.remove_instances_tags(
        created_instances, tag_keys=[tag_key_to_remove]
    )
    new_tags.pop(tag_key_to_remove)
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


async def test_remove_instance_tags_not_existing_raises(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    await _assert_no_instances_in_ec2(ec2_client)
    with pytest.raises(EC2InstanceNotFoundError):
        await simcore_ec2_api.remove_instances_tags(
            [fake_ec2_instance_data()], tag_keys=[]
        )


async def test_launch_instances_insufficient_capacity_fallback(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_type: EC2InstanceType,
    faker: Faker,
    aws_subnet_id: str,
    create_aws_subnet_id: Callable[[], Awaitable[str]],
    aws_security_group_id: str,
    aws_ami_id: str,
    mocker: MockerFixture,
):
    await _assert_no_instances_in_ec2(ec2_client)

    # Create additional valid subnets for testing
    subnet1_id = aws_subnet_id
    subnet2_id = await create_aws_subnet_id()

    # Create a config with multiple valid subnet IDs
    ec2_instance_config = EC2InstanceConfig(
        type=fake_ec2_instance_type,
        tags=faker.pydict(allowed_types=(str,)),
        startup_script=faker.pystr(),
        ami_id=aws_ami_id,
        key_name=faker.pystr(),
        security_group_ids=[aws_security_group_id],
        subnet_ids=[subnet1_id, subnet2_id],
        iam_instance_profile="",
    )

    # Mock the EC2 client to simulate InsufficientInstanceCapacity on first subnet
    original_run_instances = simcore_ec2_api.client.run_instances
    call_count = 0

    async def mock_run_instances(*args, **kwargs) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            assert kwargs["NetworkInterfaces"][0]["SubnetId"] == subnet1_id
            # First call (first subnet) - simulate insufficient capacity
            error_response: dict[str, Any] = {
                "Error": {
                    "Code": "InsufficientInstanceCapacity",
                    "Message": "Insufficient capacity.",
                },
            }
            raise botocore.exceptions.ClientError(error_response, "RunInstances")  # type: ignore
        # Second call (second subnet) - succeed normally
        assert kwargs["NetworkInterfaces"][0]["SubnetId"] == subnet2_id
        return await original_run_instances(*args, **kwargs)

    # Apply the mock
    mocker.patch.object(
        simcore_ec2_api.client, "run_instances", side_effect=mock_run_instances
    )
    instances = await simcore_ec2_api.launch_instances(
        ec2_instance_config,
        min_number_of_instances=1,
        number_of_instances=1,
    )

    # Verify that run_instances was called twice (once for each subnet)
    assert call_count == 2

    # Verify that the instance was created (in the second subnet)
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )

    # Verify the instance was created in the second subnet (since first failed)
    instance_details = await ec2_client.describe_instances(
        InstanceIds=[instances[0].id]
    )
    assert "Reservations" in instance_details
    assert len(instance_details["Reservations"]) >= 1
    assert "Instances" in instance_details["Reservations"][0]
    assert len(instance_details["Reservations"][0]["Instances"]) >= 1
    instance = instance_details["Reservations"][0]["Instances"][0]
    assert "SubnetId" in instance
    assert instance["SubnetId"] == subnet2_id


async def test_launch_instances_all_subnets_insufficient_capacity_raises_error(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_type: EC2InstanceType,
    faker: Faker,
    aws_subnet_id: str,
    create_aws_subnet_id: Callable[[], Awaitable[str]],
    aws_security_group_id: str,
    aws_ami_id: str,
    mocker: MockerFixture,
):
    await _assert_no_instances_in_ec2(ec2_client)

    # Create additional valid subnets for testing
    subnet1_id = aws_subnet_id
    subnet2_id = await create_aws_subnet_id()
    subnet3_id = await create_aws_subnet_id()

    # Create a config with multiple valid subnet IDs
    ec2_instance_config = EC2InstanceConfig(
        type=fake_ec2_instance_type,
        tags=faker.pydict(allowed_types=(str,)),
        startup_script=faker.pystr(),
        ami_id=aws_ami_id,
        key_name=faker.pystr(),
        security_group_ids=[aws_security_group_id],
        subnet_ids=[subnet1_id, subnet2_id, subnet3_id],
        iam_instance_profile="",
    )

    # Mock the EC2 client to simulate InsufficientInstanceCapacity on ALL subnets
    call_count = 0

    async def mock_run_instances(*args, **kwargs) -> Any:
        nonlocal call_count
        call_count += 1
        # Always simulate insufficient capacity
        error_response = {
            "Error": {
                "Code": "InsufficientInstanceCapacity",
                "Message": "Insufficient capacity.",
            },
        }
        raise botocore.exceptions.ClientError(error_response, "RunInstances")  # type: ignore

    # Apply the mock and expect EC2InsufficientCapacityError
    mocker.patch.object(
        simcore_ec2_api.client, "run_instances", side_effect=mock_run_instances
    )
    with pytest.raises(EC2InsufficientCapacityError) as exc_info:
        await simcore_ec2_api.launch_instances(
            ec2_instance_config,
            min_number_of_instances=1,
            number_of_instances=1,
        )

    # Verify that run_instances was called for both subnets
    assert call_count == 3

    # Verify the error contains the expected information
    assert hasattr(exc_info.value, "instance_type")
    assert exc_info.value.instance_type == fake_ec2_instance_type.name  # type: ignore

    # Verify no instances were created
    await _assert_no_instances_in_ec2(ec2_client)


async def test_launch_instances_partial_capacity_then_insufficient_capacity(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_type: EC2InstanceType,
    faker: Faker,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    mocker: MockerFixture,
):
    """Test that launch_instances handles partial capacity correctly.

    First call: ask for 3 instances (min 1) -> should get 2, no error
    Second call: ask for 3 instances (min 1) -> should raise EC2InsufficientCapacityError
    """
    await _assert_no_instances_in_ec2(ec2_client)

    # Create a config with a single subnet (as requested)
    ec2_instance_config = EC2InstanceConfig(
        type=fake_ec2_instance_type,
        tags=faker.pydict(allowed_types=(str,)),
        startup_script=faker.pystr(),
        ami_id=aws_ami_id,
        key_name=faker.pystr(),
        security_group_ids=[aws_security_group_id],
        subnet_ids=[aws_subnet_id],  # Single subnet only
        iam_instance_profile="",
    )

    # Mock the EC2 client to simulate partial capacity behavior
    original_run_instances = simcore_ec2_api.client.run_instances
    call_count = 0

    async def mock_run_instances(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call: return only 2 instances when 3 were requested
            # Simulate that the subnet has capacity for only 2 machines
            required_instances = kwargs["MaxCount"]
            kwargs_copy = kwargs.copy()
            kwargs_copy["MinCount"] = required_instances - 1
            kwargs_copy["MaxCount"] = required_instances - 1
            return await original_run_instances(*args, **kwargs_copy)

        # Second call: simulate insufficient capacity (subnet is full)
        error_response = {
            "Error": {
                "Code": "InsufficientInstanceCapacity",
                "Message": "Insufficient capacity.",
            },
        }
        raise botocore.exceptions.ClientError(error_response, "RunInstances")  # type: ignore

    # Apply the mock for the first call
    mocker.patch.object(
        simcore_ec2_api.client, "run_instances", side_effect=mock_run_instances
    )
    # First call: ask for 3 instances (min 1) -> should get 2, no error
    instances = await simcore_ec2_api.launch_instances(
        ec2_instance_config,
        min_number_of_instances=1,
        number_of_instances=3,
    )

    # Verify we got 2 instances (partial capacity)
    assert len(instances) == 2
    assert call_count == 1

    # Verify instances were created
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=2,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )

    # Second call: ask for 3 instances (min 1) -> should raise EC2InsufficientCapacityError
    with pytest.raises(EC2InsufficientCapacityError) as exc_info:
        await simcore_ec2_api.launch_instances(
            ec2_instance_config,
            min_number_of_instances=1,
            number_of_instances=3,
        )

    # Verify that run_instances was called twice total
    assert call_count == 2

    # Verify the error contains the expected information
    assert hasattr(exc_info.value, "instance_type")
    assert exc_info.value.instance_type == fake_ec2_instance_type.name  # type: ignore
    assert exc_info.value.subnet_ids == [aws_subnet_id]  # type: ignore

    # Verify still only 2 instances exist (no new ones were created)
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=2,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )


@pytest.fixture
async def with_small_subnet(
    create_aws_subnet_id: Callable[..., Awaitable[str]],
) -> tuple[str, int]:
    """Creates a subnet with a single IP address to simulate InsufficientInstanceCapacity"""
    single_ip_cidr = (
        "10.0.11.0/29"  # /29 is the minimum allowed by AWS, gives 8 addresses
    )
    return (await create_aws_subnet_id(single_ip_cidr), 8 - 5)  # 5 are reserved by AWS


async def test_launch_instances_with_small_subnet(
    simcore_ec2_api: SimcoreEC2API,
    ec2_client: EC2Client,
    fake_ec2_instance_type: EC2InstanceType,
    faker: Faker,
    with_small_subnet: tuple[str, int],
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    mocker: MockerFixture,
):
    await _assert_no_instances_in_ec2(ec2_client)
    small_subnet_id, capacity = with_small_subnet
    # Create a config with a single subnet (as requested)
    ec2_instance_config = EC2InstanceConfig(
        type=fake_ec2_instance_type,
        tags=faker.pydict(allowed_types=(str,)),
        startup_script=faker.pystr(),
        ami_id=aws_ami_id,
        key_name=faker.pystr(),
        security_group_ids=[aws_security_group_id],
        subnet_ids=[small_subnet_id, aws_subnet_id],
        iam_instance_profile="",
    )

    # first call shall work in the first subnet
    instances = await simcore_ec2_api.launch_instances(
        ec2_instance_config,
        min_number_of_instances=capacity,
        number_of_instances=capacity,
    )

    # Verify we got 2 instances (partial capacity)
    assert len(instances) == capacity

    # Verify instances were created
    await _assert_instances_in_ec2(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=capacity,
        expected_instance_type=ec2_instance_config.type,
        expected_tags=ec2_instance_config.tags,
        expected_state="running",
    )

    instances = await simcore_ec2_api.launch_instances(
        ec2_instance_config,
        min_number_of_instances=1,
        number_of_instances=1,
    )
