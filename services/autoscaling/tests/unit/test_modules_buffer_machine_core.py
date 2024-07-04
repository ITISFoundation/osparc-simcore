# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
from collections.abc import Sequence
from typing import Any, cast
from unittest import mock

import pytest
import tenacity
from aws_library.ec2.models import EC2InstanceBootSpecific
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerGenericTag
from pydantic import parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.aws_ec2 import (
    assert_autoscaled_dynamic_warm_pools_ec2_instances,
)
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.moto import patched_aiobotocore_make_api_call
from simcore_service_autoscaling.core.settings import EC2InstancesSettings
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.modules.buffer_machine_core import (
    monitor_buffer_machines,
)
from tenacity import AsyncRetrying
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType
from types_aiobotocore_ec2.type_defs import FilterTypeDef


@pytest.fixture
def pre_pull_images() -> list[DockerGenericTag]:
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
def with_ec2_instance_allowed_types_env(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(ec2_instances_allowed_types),
        },
    )
    return app_environment | envs


@pytest.fixture
def minimal_configuration(
    disabled_rabbitmq: None,
    enabled_dynamic_mode: EnvVarsDict,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ec2_instances_envs: EnvVarsDict,
    enabled_buffer_pools: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    with_ec2_instance_allowed_types_env: EnvVarsDict,
    mocked_redis_server: None,
) -> None:
    pass


@pytest.fixture
def mocked_ssm_send_command(
    mocker: MockerFixture, external_envfile_dict: EnvVarsDict
) -> mock.Mock:
    if external_envfile_dict:
        # NOTE: we run against AWS. so no need to mock
        return mock.Mock()
    return mocker.patch(
        "aiobotocore.client.AioBaseClient._make_api_call",
        side_effect=patched_aiobotocore_make_api_call,
        autospec=True,
    )


async def test_external_env_setup(minimal_configuration: None, ec2_client: EC2Client):
    print(await ec2_client.describe_account_attributes())


@pytest.mark.xfail(
    reason="moto does not handle mocking of SSM SendCommand completely. "
    "TIP: if this test passes, it will mean Moto now handles it."
    " Delete 'mocked_ssm_send_command' fixture if that is the case and remove this test"
)
async def test_if_send_command_is_mocked_by_moto(
    minimal_configuration: None,
    initialized_app: FastAPI,
    ec2_client: EC2Client,
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
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
        expected_instance_type=next(iter(ec2_instances_allowed_types)),
        expected_instance_state="running",
        expected_additional_tag_keys=[],
        instance_filters=None,
    )

    # 2. this should generate a failure as current version of moto does not handle this
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )


async def test_monitor_buffer_machines(
    mocked_ssm_send_command: mock.Mock,
    minimal_configuration: None,
    initialized_app: FastAPI,
    ec2_client: EC2Client,
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
    ec2_instance_custom_tags: dict[str, str],
    buffer_count: int,
):
    # 0. we have no instances now
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
        expected_instance_type=next(iter(ec2_instances_allowed_types)),
        expected_instance_state="running",
        expected_additional_tag_keys=[
            *ec2_instance_custom_tags.keys(),
        ],
        instance_filters=None,
    )

    # 2. this should now run a SSM command for pulling
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
            *ec2_instance_custom_tags.keys(),
        ],
        instance_filters=None,
    )

    # 3. is the command finished?
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
            *ec2_instance_custom_tags.keys(),
        ],
        instance_filters=None,
    )


@pytest.fixture
def ec2_pytest_tag_key() -> str:
    return "pytest"


@pytest.fixture
def ec2_instances_allowed_types(
    faker: Faker,
    pre_pull_images: list[DockerGenericTag],
    buffer_count: int,
    external_ec2_instances_allowed_types: None | dict[str, EC2InstanceBootSpecific],
) -> dict[InstanceTypeType, Any]:
    if not external_ec2_instances_allowed_types:
        return {
            "t2.micro": {
                "ami_id": faker.pystr(),
                "pre_pull_images": pre_pull_images,
                "buffer_count": buffer_count,
            }
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
        len(allowed_ec2_types_with_buffer_defined) == 1
    ), "more than one type with buffer is disallowed in this test!"
    return {
        cast(InstanceTypeType, k): v
        for k, v in allowed_ec2_types_with_buffer_defined.items()
    }


@pytest.fixture
def with_ec2_pytest_tag_key_as_custom_tag(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    ec2_pytest_tag_key: str,
) -> EnvVarsDict:
    monkeypatch.setenv(
        "EC2_INSTANCES_CUSTOM_TAGS",
        json.dumps({ec2_pytest_tag_key: "true"}),
    )
    return app_environment


@pytest.fixture
def instance_type_filters(
    with_ec2_pytest_tag_key_as_custom_tag: EnvVarsDict, ec2_pytest_tag_key: str
) -> Sequence[FilterTypeDef]:
    return [
        FilterTypeDef(
            Name="tag-key",
            Values=[
                ec2_pytest_tag_key,
            ],
        ),
        FilterTypeDef(
            Name="instance-state-name",
            Values=["pending", "running", "stopped"],
        ),
    ]


@pytest.fixture
def external_ec2_instances_allowed_types(
    external_envfile_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None | dict[str, EC2InstanceBootSpecific]:
    if not external_envfile_dict:
        return None
    with monkeypatch.context() as patch:
        setenvs_from_dict(patch, {**external_envfile_dict})
        settings = EC2InstancesSettings.create_from_envs()
    return settings.EC2_INSTANCES_ALLOWED_TYPES


@pytest.fixture
def buffer_count(
    faker: Faker,
    external_ec2_instances_allowed_types: None | dict[str, EC2InstanceBootSpecific],
) -> int:
    if not external_ec2_instances_allowed_types:
        return faker.pyint(min_value=1, max_value=9)

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
        len(allowed_ec2_types_with_buffer_defined) == 1
    ), "more than one type with buffer is disallowed in this test!"
    return next(iter(allowed_ec2_types_with_buffer_defined.values())).buffer_count


async def test_monitor_buffer_machines_against_aws(
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    external_envfile_dict: EnvVarsDict,
    buffer_count: int,
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
    instance_type_filters: Sequence[FilterTypeDef],
    ec2_client: EC2Client,
    ec2_pytest_tag_key: str,
    initialized_app: FastAPI,
):
    if not external_envfile_dict:
        pytest.skip(
            "This test is only for use directly with AWS server, please define --external-envfile"
        )

    # in this test we consider only one type to have buffers

    # 0. we have no instances now
    all_instances = await ec2_client.describe_instances(Filters=instance_type_filters)
    assert not all_instances["Reservations"]

    # 1. run, this will create as many buffer machines as needed
    with log_context(logging.INFO, "create buffer machines"):
        await monitor_buffer_machines(
            initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
        with log_context(
            logging.INFO, f"waiting for {buffer_count} buffer instances to be running"
        ) as ctx:
            async for attempt in AsyncRetrying(
                wait=tenacity.wait_fixed(5),
                stop=tenacity.stop_after_delay(120),
                retry=tenacity.retry_if_exception_type(AssertionError),
                reraise=True,
                before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
                after=tenacity.after_log(ctx.logger, logging.INFO),
            ):
                with attempt:
                    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
                        ec2_client,
                        expected_num_reservations=1,
                        expected_num_instances=buffer_count,
                        expected_instance_type=next(iter(ec2_instances_allowed_types)),
                        expected_instance_state="running",
                        expected_additional_tag_keys=[ec2_pytest_tag_key],
                        instance_filters=instance_type_filters,
                    )
                    ctx.logger.info(
                        "%s",
                        f"{buffer_count} buffer now running after {attempt.retry_state.retry_object.statistics}",
                    )

    # 2. this should now run a SSM command for pulling
    with log_context(logging.INFO, "run SSM commands for pulling") as ctx:
        async for attempt in AsyncRetrying(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(120),
            retry=tenacity.retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
            after=tenacity.after_log(ctx.logger, logging.INFO),
        ):
            with attempt:
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
                        ec2_pytest_tag_key,
                    ],
                    instance_filters=instance_type_filters,
                )
                ctx.logger.info(
                    "%s",
                    f"command set after {attempt.retry_state.retry_object.statistics}",
                )

    # 3. is the command finished?
    with log_context(logging.INFO, "wait for SSM commands for to finish") as ctx:
        async for attempt in AsyncRetrying(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(120),
            retry=tenacity.retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
            after=tenacity.after_log(ctx.logger, logging.INFO),
        ):
            with attempt:
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
                        ec2_pytest_tag_key,
                    ],
                    instance_filters=instance_type_filters,
                )
                ctx.logger.info(
                    "%s",
                    f"command set after {attempt.retry_state.retry_object.statistics}",
                )
