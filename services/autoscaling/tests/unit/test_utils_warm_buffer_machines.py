# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aws_library.ec2 import AWSTagValue, EC2Tags
from fastapi import FastAPI
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    BUFFER_MACHINE_TAG_KEY,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
)
from simcore_service_autoscaling.modules.cluster_scaling._provider_computational import (
    ComputationalAutoscalingProvider,
)
from simcore_service_autoscaling.modules.cluster_scaling._provider_dynamic import (
    DynamicAutoscalingProvider,
)
from simcore_service_autoscaling.utils.warm_buffer_machines import (
    get_activated_warm_buffer_ec2_tags,
    get_deactivated_warm_buffer_ec2_tags,
    is_warm_buffer_machine,
)


def test_get_activated_buffer_ec2_tags_dynamic(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    initialized_app: FastAPI,
):
    auto_scaling_mode = DynamicAutoscalingProvider()
    activated_buffer_tags = get_activated_warm_buffer_ec2_tags(
        auto_scaling_mode.get_ec2_tags(initialized_app)
    )
    assert (
        auto_scaling_mode.get_ec2_tags(initialized_app)
        | ACTIVATED_BUFFER_MACHINE_EC2_TAGS
    ) == activated_buffer_tags


def test_get_deactivated_buffer_ec2_tags_dynamic(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    initialized_app: FastAPI,
):
    auto_scaling_mode = DynamicAutoscalingProvider()
    deactivated_buffer_tags = get_deactivated_warm_buffer_ec2_tags(
        auto_scaling_mode.get_ec2_tags(initialized_app)
    )
    # when deactivated the buffer EC2 name has an additional -buffer suffix
    expected_tags = (
        auto_scaling_mode.get_ec2_tags(initialized_app)
        | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    )
    assert "Name" in expected_tags
    expected_tags["Name"] = TypeAdapter(AWSTagValue).validate_python(
        str(expected_tags["Name"]) + "-buffer"
    )
    assert expected_tags == deactivated_buffer_tags


def test_get_activated_buffer_ec2_tags_computational(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_computational_mode: EnvVarsDict,
    initialized_app: FastAPI,
):
    auto_scaling_mode = ComputationalAutoscalingProvider()
    activated_buffer_tags = get_activated_warm_buffer_ec2_tags(
        auto_scaling_mode.get_ec2_tags(initialized_app)
    )
    assert (
        auto_scaling_mode.get_ec2_tags(initialized_app)
        | ACTIVATED_BUFFER_MACHINE_EC2_TAGS
    ) == activated_buffer_tags


def test_get_deactivated_buffer_ec2_tags_computational(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_computational_mode: EnvVarsDict,
    initialized_app: FastAPI,
):
    auto_scaling_mode = ComputationalAutoscalingProvider()
    deactivated_buffer_tags = get_deactivated_warm_buffer_ec2_tags(
        auto_scaling_mode.get_ec2_tags(initialized_app)
    )
    # when deactivated the buffer EC2 name has an additional -buffer suffix
    expected_tags = (
        auto_scaling_mode.get_ec2_tags(initialized_app)
        | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    )
    assert "Name" in expected_tags
    expected_tags["Name"] = TypeAdapter(AWSTagValue).validate_python(
        str(expected_tags["Name"]) + "-buffer"
    )
    assert expected_tags == deactivated_buffer_tags


@pytest.mark.parametrize(
    "tags, expected_is_buffer",
    [
        ({"whatever_key": "whatever_value"}, False),
        ({BUFFER_MACHINE_TAG_KEY: "whatever_value"}, True),
    ],
)
def test_is_buffer_machine(tags: EC2Tags, expected_is_buffer: bool):
    assert is_warm_buffer_machine(tags) is expected_is_buffer
