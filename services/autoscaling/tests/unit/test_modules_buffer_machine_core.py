# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime
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
from fastapi.encoders import jsonable_encoder
from models_library.docker import DockerGenericTag
from pydantic import parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.aws_ec2 import (
    assert_autoscaled_dynamic_warm_pools_ec2_instances,
)
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.core.settings import EC2InstancesSettings
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.modules.buffer_machine_core import (
    monitor_buffer_machines,
)
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
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                jsonable_encoder(ec2_instances_allowed_types)
            ),
        },
    )
    return app_environment | envs


@pytest.fixture
def minimal_configuration(
    disabled_rabbitmq: None,
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


async def test_monitor_buffer_machines(
    minimal_configuration: None,
    ec2_client: EC2Client,
    buffer_count: int,
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
    instance_type_filters: Sequence[FilterTypeDef],
    ec2_instance_custom_tags: dict[str, str],
    mock_wait_for_has_instance_completed_cloud_init: mock.Mock | None,
    initialized_app: FastAPI,
):
    # 0. we have no instances now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

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
                stop=tenacity.stop_after_delay(120),
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
                    expected_additional_tag_keys=list(ec2_instance_custom_tags),
                    instance_filters=instance_type_filters,
                )

            await _assert_buffer_machines_running()

    # 2. this should now run a SSM command for pulling
    with log_context(logging.INFO, "run SSM commands for pulling") as ctx:

        @tenacity.retry(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(120),
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
                instance_filters=instance_type_filters,
            )

        await _assert_run_ssm_command_for_pulling()

    # 3. is the command finished?
    with log_context(logging.INFO, "wait for SSM commands to finish") as ctx:

        @tenacity.retry(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(datetime.timedelta(minutes=10)),
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
                expected_additional_tag_keys=list(ec2_instance_custom_tags),
                instance_filters=instance_type_filters,
            )

        await _assert_wait_for_ssm_command_to_finish()


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


@pytest.fixture
def skip_if_external_envfile_dict(external_envfile_dict: EnvVarsDict) -> None:
    if not external_envfile_dict:
        pytest.skip("Skipping test since external-envfile is not set")


async def test_monitor_buffer_machines_against_aws(
    skip_if_external_envfile_dict: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    external_envfile_dict: EnvVarsDict,
    ec2_client: EC2Client,
    buffer_count: int,
    ec2_instances_allowed_types: dict[InstanceTypeType, Any],
    instance_type_filters: Sequence[FilterTypeDef],
    ec2_instance_custom_tags: dict[str, str],
    initialized_app: FastAPI,
):
    if not external_envfile_dict:
        pytest.skip(
            "This test is only for use directly with AWS server, please define --external-envfile"
        )

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

            @tenacity.retry(
                wait=tenacity.wait_fixed(5),
                stop=tenacity.stop_after_delay(120),
                retry=tenacity.retry_if_exception_type(AssertionError),
                reraise=True,
                before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
                after=tenacity.after_log(ctx.logger, logging.INFO),
            )
            async def _assert_buffer_machines_running():
                await assert_autoscaled_dynamic_warm_pools_ec2_instances(
                    ec2_client,
                    expected_num_reservations=1,
                    expected_num_instances=buffer_count,
                    expected_instance_type=next(iter(ec2_instances_allowed_types)),
                    expected_instance_state="running",
                    expected_additional_tag_keys=list(ec2_instance_custom_tags),
                    instance_filters=instance_type_filters,
                )

            await _assert_buffer_machines_running()

    # 2. this should now run a SSM command for pulling
    with log_context(logging.INFO, "run SSM commands for pulling") as ctx:

        @tenacity.retry(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(120),
            retry=tenacity.retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
            after=tenacity.after_log(ctx.logger, logging.INFO),
        )
        async def _assert_ssm_command_for_pulling():
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
                instance_filters=instance_type_filters,
            )

        await _assert_ssm_command_for_pulling()

    # 3. is the command finished?
    with log_context(logging.INFO, "wait for SSM commands to finish") as ctx:

        @tenacity.retry(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(datetime.timedelta(minutes=10)),
            retry=tenacity.retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
            after=tenacity.after_log(ctx.logger, logging.INFO),
        )
        async def _assert_wait_for_ssm_command_to_finish():
            await monitor_buffer_machines(
                initialized_app, auto_scaling_mode=DynamicAutoscaling()
            )
            await assert_autoscaled_dynamic_warm_pools_ec2_instances(
                ec2_client,
                expected_num_reservations=1,
                expected_num_instances=buffer_count,
                expected_instance_type=next(iter(ec2_instances_allowed_types)),
                expected_instance_state="stopped",
                expected_additional_tag_keys=list(ec2_instance_custom_tags),
                instance_filters=instance_type_filters,
            )

        await _assert_wait_for_ssm_command_to_finish()
