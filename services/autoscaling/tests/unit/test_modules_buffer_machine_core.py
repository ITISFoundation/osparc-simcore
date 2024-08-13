# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import datetime
import json
import logging
import random
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any
from unittest import mock

import pytest
import tenacity
from aws_library.ec2 import AWSTagKey, EC2InstanceBootSpecific
from faker import Faker
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.docker import DockerGenericTag
from models_library.utils.json_serialization import json_dumps
from pydantic import parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.aws_ec2 import (
    assert_autoscaled_dynamic_warm_pools_ec2_instances,
)
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.modules.buffer_machines_pool_core import (
    _PRE_PULLED_IMAGES_EC2_TAG_KEY,
    monitor_buffer_machines,
)
from simcore_service_autoscaling.utils.buffer_machines_pool_core import (
    get_deactivated_buffer_ec2_tags,
)
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType
from types_aiobotocore_ec2.type_defs import FilterTypeDef, TagTypeDef


@pytest.fixture
def fake_pre_pull_images() -> list[DockerGenericTag]:
    return parse_obj_as(
        list[DockerGenericTag],
        [
            "nginx:latest",
            "itisfoundation/my-very-nice-service:latest",
            "simcore/services/dynamic/another-nice-one:2.4.5",
            "asd",
        ],
    )


@pytest.fixture
def ec2_instances_allowed_types_with_only_1_buffered(
    faker: Faker,
    fake_pre_pull_images: list[DockerGenericTag],
    external_ec2_instances_allowed_types: None | dict[str, EC2InstanceBootSpecific],
) -> dict[InstanceTypeType, EC2InstanceBootSpecific]:
    if not external_ec2_instances_allowed_types:
        return {
            "t2.micro": EC2InstanceBootSpecific(
                ami_id=faker.pystr(),
                pre_pull_images=fake_pre_pull_images,
                buffer_count=faker.pyint(min_value=1, max_value=10),
            )
        }

    allowed_ec2_types = external_ec2_instances_allowed_types
    allowed_ec2_types_with_buffer_defined = dict(
        filter(
            lambda instance_type_and_settings: instance_type_and_settings[
                1
            ].buffer_count
            > 0,
            allowed_ec2_types.items(),
        )
    )
    assert (
        allowed_ec2_types_with_buffer_defined
    ), "one type with buffer is needed for the tests!"
    assert (
        len(allowed_ec2_types_with_buffer_defined) == 1
    ), "more than one type with buffer is disallowed in this test!"
    return {
        parse_obj_as(InstanceTypeType, k): v
        for k, v in allowed_ec2_types_with_buffer_defined.items()
    }


@pytest.fixture
def with_ec2_instance_allowed_types_env(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any],
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                jsonable_encoder(ec2_instances_allowed_types_with_only_1_buffered)
            ),
        },
    )
    return app_environment | envs


@pytest.fixture
def minimal_configuration(
    disabled_rabbitmq: None,
    disable_buffers_pool_background_task: None,
    enabled_dynamic_mode: EnvVarsDict,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ec2_instances_envs: EnvVarsDict,
    with_enabled_buffer_pools: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    with_ec2_instance_allowed_types_env: EnvVarsDict,
    mocked_redis_server: None,
) -> None:
    pass


@pytest.fixture(autouse=True)
def set_log_levels_for_noisy_libraries() -> None:
    # Reduce the log level for 'werkzeug'
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


@pytest.mark.xfail(
    reason="moto does not handle mocking of SSM SendCommand completely. "
    "TIP: if this test passes, it will mean Moto now handles it."
    " Delete 'mocked_ssm_send_command' fixture if that is the case and remove this test"
)
async def test_if_send_command_is_mocked_by_moto(
    minimal_configuration: None,
    initialized_app: FastAPI,
    ec2_client: EC2Client,
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any],
    buffer_count: int,
):
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # 1. run, this will create as many buffer machines as needed
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=next(
            iter(ec2_instances_allowed_types_with_only_1_buffered)
        ),
        expected_instance_state="running",
        expected_additional_tag_keys=[],
        expected_pre_pulled_images=[],
        instance_filters=None,
    )

    # 2. this should generate a failure as current version of moto does not handle this
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )


@pytest.fixture
def mock_wait_for_has_instance_completed_cloud_init(
    external_envfile_dict: EnvVarsDict, initialized_app: FastAPI, mocker: MockerFixture
) -> mock.Mock | None:
    if external_envfile_dict:
        return None
    return mocker.patch(
        "aws_library.ssm._client.SimcoreSSMAPI.wait_for_has_instance_completed_cloud_init",
        autospec=True,
        return_value=True,
    )


@pytest.fixture
def instance_type_filters(
    ec2_instance_custom_tags: dict[str, str],
) -> Sequence[FilterTypeDef]:
    return [
        *[
            FilterTypeDef(
                Name="tag-key",
                Values=[tag_key],
            )
            for tag_key in ec2_instance_custom_tags
        ],
        FilterTypeDef(
            Name="instance-state-name",
            Values=["pending", "running", "stopped"],
        ),
    ]


async def _test_monitor_buffer_machines(
    *,
    ec2_client: EC2Client,
    instance_type_filters: Sequence[FilterTypeDef],
    initialized_app: FastAPI,
    buffer_count: int,
    pre_pulled_images: list[DockerGenericTag],
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
    ec2_instance_custom_tags: dict[str, str],
    run_against_moto: bool,
):
    # 0. we have no instances now
    all_instances = await ec2_client.describe_instances(Filters=instance_type_filters)
    assert not all_instances[
        "Reservations"
    ], f"There should be no instances at the start of the test. Found following instance ids: {[i['InstanceId'] for r in all_instances['Reservations'] if 'Instances' in r for i in r['Instances'] if 'InstanceId' in i]}"

    # 1. run, this will create as many buffer machines as needed
    with log_context(logging.INFO, "create buffer machines"):
        await monitor_buffer_machines(
            initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
        with log_context(
            logging.INFO, f"waiting for {buffer_count} buffer instances to be running"
        ) as ctx:

            @tenacity.retry(
                wait=tenacity.wait_fixed(5),
                stop=tenacity.stop_after_delay(5 if run_against_moto else 120),
                retry=tenacity.retry_if_exception_type(AssertionError),
                reraise=True,
                before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
                after=tenacity.after_log(ctx.logger, logging.INFO),
            )
            async def _assert_buffer_machines_running() -> None:
                await assert_autoscaled_dynamic_warm_pools_ec2_instances(
                    ec2_client,
                    expected_num_reservations=1,
                    expected_num_instances=buffer_count,
                    expected_instance_type=next(iter(ec2_instances_allowed_types)),
                    expected_instance_state="running",
                    expected_additional_tag_keys=[
                        *list(ec2_instance_custom_tags),
                    ],
                    expected_pre_pulled_images=None,
                    instance_filters=instance_type_filters,
                )

            await _assert_buffer_machines_running()

    # 2. this should now run a SSM command for pulling
    with log_context(logging.INFO, "run SSM commands for pulling") as ctx:

        @tenacity.retry(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(5 if run_against_moto else 120),
            retry=tenacity.retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
            after=tenacity.after_log(ctx.logger, logging.INFO),
        )
        async def _assert_run_ssm_command_for_pulling() -> None:
            await monitor_buffer_machines(
                initialized_app, auto_scaling_mode=DynamicAutoscaling()
            )
            await assert_autoscaled_dynamic_warm_pools_ec2_instances(
                ec2_client,
                expected_num_reservations=1,
                expected_num_instances=buffer_count,
                expected_instance_type=next(iter(ec2_instances_allowed_types)),
                expected_instance_state="running",
                expected_additional_tag_keys=[
                    "pulling",
                    "ssm-command-id",
                    *list(ec2_instance_custom_tags),
                ],
                expected_pre_pulled_images=None,
                instance_filters=instance_type_filters,
            )

        if pre_pulled_images:
            await _assert_run_ssm_command_for_pulling()

    # 3. is the command finished?
    with log_context(
        logging.INFO, "wait for SSM commands and the machine to be stopped to finish"
    ) as ctx:

        @tenacity.retry(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(
                5 if run_against_moto else datetime.timedelta(minutes=10)
            ),
            retry=tenacity.retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
            after=tenacity.after_log(ctx.logger, logging.INFO),
        )
        async def _assert_wait_for_ssm_command_to_finish() -> None:
            await monitor_buffer_machines(
                initialized_app, auto_scaling_mode=DynamicAutoscaling()
            )
            await assert_autoscaled_dynamic_warm_pools_ec2_instances(
                ec2_client,
                expected_num_reservations=1,
                expected_num_instances=buffer_count,
                expected_instance_type=next(iter(ec2_instances_allowed_types)),
                expected_instance_state="stopped",
                expected_additional_tag_keys=[
                    _PRE_PULLED_IMAGES_EC2_TAG_KEY,
                    *list(ec2_instance_custom_tags),
                ],
                expected_pre_pulled_images=pre_pulled_images,
                instance_filters=instance_type_filters,
            )

        await _assert_wait_for_ssm_command_to_finish()


async def test_monitor_buffer_machines(
    minimal_configuration: None,
    ec2_client: EC2Client,
    buffer_count: int,
    pre_pull_images: list[DockerGenericTag],
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any],
    instance_type_filters: Sequence[FilterTypeDef],
    ec2_instance_custom_tags: dict[str, str],
    mock_wait_for_has_instance_completed_cloud_init: mock.Mock | None,
    initialized_app: FastAPI,
):
    await _test_monitor_buffer_machines(
        ec2_client=ec2_client,
        instance_type_filters=instance_type_filters,
        initialized_app=initialized_app,
        buffer_count=buffer_count,
        pre_pulled_images=pre_pull_images,
        ec2_instances_allowed_types=ec2_instances_allowed_types_with_only_1_buffered,
        ec2_instance_custom_tags=ec2_instance_custom_tags,
        run_against_moto=True,
    )


@pytest.fixture
async def create_buffer_machines(
    ec2_client: EC2Client,
    aws_ami_id: str,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
) -> Callable[
    [int, InstanceTypeType, InstanceStateNameType, list[DockerGenericTag]],
    Awaitable[list[str]],
]:
    async def _do(
        num: int,
        instance_type: InstanceTypeType,
        instance_state_name: InstanceStateNameType,
        pre_pull_images: list[DockerGenericTag],
    ) -> list[str]:
        assert app_settings.AUTOSCALING_EC2_INSTANCES

        assert instance_state_name in [
            "running",
            "stopped",
        ], "only 'running' and 'stopped' are supported for testing"

        resource_tags: list[TagTypeDef] = [
            {"Key": tag_key, "Value": tag_value}
            for tag_key, tag_value in get_deactivated_buffer_ec2_tags(
                initialized_app, DynamicAutoscaling()
            ).items()
        ]
        if pre_pull_images is not None and instance_state_name == "stopped":
            resource_tags.append(
                {
                    "Key": _PRE_PULLED_IMAGES_EC2_TAG_KEY,
                    "Value": f"{json_dumps(pre_pull_images)}",
                }
            )
        with log_context(
            logging.INFO, f"creating {num} buffer machines of {instance_type}"
        ):
            instances = await ec2_client.run_instances(
                ImageId=aws_ami_id,
                MaxCount=num,
                MinCount=num,
                InstanceType=instance_type,
                KeyName=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME,
                SecurityGroupIds=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SECURITY_GROUP_IDS,
                SubnetId=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SUBNET_ID,
                IamInstanceProfile={
                    "Arn": app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ATTACHED_IAM_PROFILE
                },
                TagSpecifications=[
                    {"ResourceType": "instance", "Tags": resource_tags},
                    {"ResourceType": "volume", "Tags": resource_tags},
                    {"ResourceType": "network-interface", "Tags": resource_tags},
                ],
                UserData="echo 'I am pytest'",
            )
            instance_ids = [
                i["InstanceId"] for i in instances["Instances"] if "InstanceId" in i
            ]

        waiter = ec2_client.get_waiter("instance_exists")
        await waiter.wait(InstanceIds=instance_ids)
        instances = await ec2_client.describe_instances(InstanceIds=instance_ids)
        assert "Reservations" in instances
        assert instances["Reservations"]
        assert "Instances" in instances["Reservations"][0]
        assert len(instances["Reservations"][0]["Instances"]) == num
        for instance in instances["Reservations"][0]["Instances"]:
            assert "State" in instance
            assert "Name" in instance["State"]
            assert instance["State"]["Name"] == "running"

        if instance_state_name == "stopped":
            await ec2_client.stop_instances(InstanceIds=instance_ids)
            instances = await ec2_client.describe_instances(InstanceIds=instance_ids)
            assert "Reservations" in instances
            assert instances["Reservations"]
            assert "Instances" in instances["Reservations"][0]
            assert len(instances["Reservations"][0]["Instances"]) == num
            for instance in instances["Reservations"][0]["Instances"]:
                assert "State" in instance
                assert "Name" in instance["State"]
                assert instance["State"]["Name"] == "stopped"

        return instance_ids

    return _do


@dataclass
class _BufferMachineParams:
    instance_state_name: InstanceStateNameType
    pre_pulled_images: list[DockerGenericTag] | None
    tag_keys: list[AWSTagKey]


@pytest.mark.parametrize(
    "expected_buffer_params",
    [
        _BufferMachineParams("running", None, []),
        _BufferMachineParams(
            "stopped",
            [],
            [parse_obj_as(AWSTagKey, "io.simcore.autoscaling.pre_pulled_images")],
        ),
    ],
)
async def test_monitor_buffer_machines_terminates_supernumerary_instances(
    minimal_configuration: None,
    ec2_client: EC2Client,
    buffer_count: int,
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any],
    instance_type_filters: Sequence[FilterTypeDef],
    ec2_instance_custom_tags: dict[str, str],
    initialized_app: FastAPI,
    create_buffer_machines: Callable[
        [int, InstanceTypeType, InstanceStateNameType, list[DockerGenericTag]],
        Awaitable[list[str]],
    ],
    expected_buffer_params: _BufferMachineParams,
):
    # have too many machines of accepted type
    buffer_machines = await create_buffer_machines(
        buffer_count + 5,
        next(iter(list(ec2_instances_allowed_types_with_only_1_buffered))),
        expected_buffer_params.instance_state_name,
        [],
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=len(buffer_machines),
        expected_instance_type=next(
            iter(ec2_instances_allowed_types_with_only_1_buffered)
        ),
        expected_instance_state=expected_buffer_params.instance_state_name,
        expected_additional_tag_keys=[
            *list(ec2_instance_custom_tags),
            *expected_buffer_params.tag_keys,
        ],
        expected_pre_pulled_images=expected_buffer_params.pre_pulled_images,
        instance_filters=instance_type_filters,
    )
    # this will terminate the supernumerary instances and start new ones
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=next(
            iter(ec2_instances_allowed_types_with_only_1_buffered)
        ),
        expected_instance_state=expected_buffer_params.instance_state_name,
        expected_additional_tag_keys=[
            *list(ec2_instance_custom_tags),
            *expected_buffer_params.tag_keys,
        ],
        expected_pre_pulled_images=expected_buffer_params.pre_pulled_images,
        instance_filters=instance_type_filters,
    )


async def test_monitor_buffer_machines_terminates_instances_with_incorrect_pre_pulled_images(
    minimal_configuration: None,
    ec2_client: EC2Client,
    buffer_count: int,
    pre_pull_images: list[DockerGenericTag],
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any],
    instance_type_filters: Sequence[FilterTypeDef],
    ec2_instance_custom_tags: dict[str, str],
    initialized_app: FastAPI,
    create_buffer_machines: Callable[
        [int, InstanceTypeType, InstanceStateNameType, list[DockerGenericTag]],
        Awaitable[list[str]],
    ],
):
    # have machines of correct type with missing pre-pulled images
    assert (
        len(pre_pull_images) > 1
    ), "this test relies on pre-pulled images being filled with more than 1 image"
    buffer_machines = await create_buffer_machines(
        buffer_count + 5,
        next(iter(list(ec2_instances_allowed_types_with_only_1_buffered))),
        "stopped",
        pre_pull_images[:-1],
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=len(buffer_machines),
        expected_instance_type=next(
            iter(ec2_instances_allowed_types_with_only_1_buffered)
        ),
        expected_instance_state="stopped",
        expected_additional_tag_keys=[
            *list(ec2_instance_custom_tags),
            "io.simcore.autoscaling.pre_pulled_images",
        ],
        expected_pre_pulled_images=pre_pull_images[:-1],
        instance_filters=instance_type_filters,
    )
    # this will terminate the wrong instances and start new ones and pre-pull the new set of images
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=next(
            iter(ec2_instances_allowed_types_with_only_1_buffered)
        ),
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        expected_pre_pulled_images=None,  # NOTE: these are not pre-pulled yet, just started
        instance_filters=instance_type_filters,
    )


@pytest.fixture
def unneeded_instance_type(
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any],
) -> InstanceTypeType:
    random_type = next(iter(ec2_instances_allowed_types_with_only_1_buffered))
    while random_type in ec2_instances_allowed_types_with_only_1_buffered:
        random_type = random.choice(InstanceTypeType.__args__)  # noqa: S311
    return random_type


@pytest.mark.parametrize(
    "expected_buffer_params",
    [
        _BufferMachineParams("running", None, []),
        _BufferMachineParams(
            "stopped",
            [],
            [parse_obj_as(AWSTagKey, "io.simcore.autoscaling.pre_pulled_images")],
        ),
    ],
)
async def test_monitor_buffer_machines_terminates_unneeded_pool(
    minimal_configuration: None,
    ec2_client: EC2Client,
    buffer_count: int,
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any],
    instance_type_filters: Sequence[FilterTypeDef],
    ec2_instance_custom_tags: dict[str, str],
    initialized_app: FastAPI,
    create_buffer_machines: Callable[
        [int, InstanceTypeType, InstanceStateNameType, list[DockerGenericTag]],
        Awaitable[list[str]],
    ],
    unneeded_instance_type: InstanceTypeType,
    expected_buffer_params: _BufferMachineParams,
):
    # have machines of unneeded type
    buffer_machines_unneeded = await create_buffer_machines(
        5, unneeded_instance_type, expected_buffer_params.instance_state_name, []
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=len(buffer_machines_unneeded),
        expected_instance_type=unneeded_instance_type,
        expected_instance_state=expected_buffer_params.instance_state_name,
        expected_additional_tag_keys=[
            *list(ec2_instance_custom_tags),
            *expected_buffer_params.tag_keys,
        ],
        expected_pre_pulled_images=expected_buffer_params.pre_pulled_images,
        instance_filters=instance_type_filters,
    )

    # this will terminate the unwanted buffer pool and replace with the expected ones
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=next(
            iter(ec2_instances_allowed_types_with_only_1_buffered)
        ),
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        expected_pre_pulled_images=None,
        instance_filters=instance_type_filters,
    )


@pytest.fixture
def buffer_count(
    ec2_instances_allowed_types_with_only_1_buffered: dict[
        InstanceTypeType, EC2InstanceBootSpecific
    ],
) -> int:
    def _by_buffer_count(
        instance_type_and_settings: tuple[InstanceTypeType, EC2InstanceBootSpecific]
    ) -> bool:
        _, boot_specific = instance_type_and_settings
        return boot_specific.buffer_count > 0

    allowed_ec2_types = ec2_instances_allowed_types_with_only_1_buffered
    allowed_ec2_types_with_buffer_defined = dict(
        filter(_by_buffer_count, allowed_ec2_types.items())
    )
    assert allowed_ec2_types_with_buffer_defined, "you need one type with buffer"
    assert (
        len(allowed_ec2_types_with_buffer_defined) == 1
    ), "more than one type with buffer is disallowed in this test!"
    return next(iter(allowed_ec2_types_with_buffer_defined.values())).buffer_count


@pytest.fixture
def pre_pull_images(
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any]
) -> list[DockerGenericTag]:
    allowed_ec2_types = ec2_instances_allowed_types_with_only_1_buffered
    allowed_ec2_types_with_pre_pull_images_defined = dict(
        filter(
            lambda instance_type_and_settings: instance_type_and_settings[
                1
            ].pre_pull_images,
            allowed_ec2_types.items(),
        )
    )
    assert (
        len(allowed_ec2_types_with_pre_pull_images_defined) <= 1
    ), "more than one type with pre-pulled-images is disallowed in this test!"

    if allowed_ec2_types_with_pre_pull_images_defined:
        return next(
            iter(allowed_ec2_types_with_pre_pull_images_defined.values())
        ).pre_pull_images
    return []


async def test_monitor_buffer_machines_against_aws(
    skip_if_external_envfile_dict: None,
    disable_buffers_pool_background_task: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    external_envfile_dict: EnvVarsDict,
    ec2_client: EC2Client,
    buffer_count: int,
    pre_pull_images: list[DockerGenericTag],
    ec2_instances_allowed_types_with_only_1_buffered: dict[InstanceTypeType, Any],
    instance_type_filters: Sequence[FilterTypeDef],
    ec2_instance_custom_tags: dict[str, str],
    initialized_app: FastAPI,
):
    await _test_monitor_buffer_machines(
        ec2_client=ec2_client,
        instance_type_filters=instance_type_filters,
        initialized_app=initialized_app,
        buffer_count=buffer_count,
        pre_pulled_images=pre_pull_images,
        ec2_instances_allowed_types=ec2_instances_allowed_types_with_only_1_buffered,
        ec2_instance_custom_tags=ec2_instance_custom_tags,
        run_against_moto=False,
    )
