# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aws_library.ec2 import AWSTagValue, EC2InstanceBootSpecific, EC2Tags
from fastapi import FastAPI
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    WARM_BUFFER_MACHINE_TAG_KEY,
)
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.modules.cluster_scaling._provider_computational import (
    ComputationalAutoscalingProvider,
)
from simcore_service_autoscaling.modules.cluster_scaling._provider_dynamic import (
    DynamicAutoscalingProvider,
)
from simcore_service_autoscaling.utils.warm_buffer_machines import (
    ec2_warm_buffer_startup_script,
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
    activated_buffer_tags = get_activated_warm_buffer_ec2_tags(auto_scaling_mode.get_ec2_tags(initialized_app))
    assert (
        auto_scaling_mode.get_ec2_tags(initialized_app) | ACTIVATED_BUFFER_MACHINE_EC2_TAGS
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
    deactivated_buffer_tags = get_deactivated_warm_buffer_ec2_tags(auto_scaling_mode.get_ec2_tags(initialized_app))
    # when deactivated the buffer EC2 name has an additional -buffer suffix
    expected_tags = auto_scaling_mode.get_ec2_tags(initialized_app) | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    assert "Name" in expected_tags
    expected_tags["Name"] = TypeAdapter(AWSTagValue).validate_python(str(expected_tags["Name"]) + "-buffer")
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
    activated_buffer_tags = get_activated_warm_buffer_ec2_tags(auto_scaling_mode.get_ec2_tags(initialized_app))
    assert (
        auto_scaling_mode.get_ec2_tags(initialized_app) | ACTIVATED_BUFFER_MACHINE_EC2_TAGS
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
    deactivated_buffer_tags = get_deactivated_warm_buffer_ec2_tags(auto_scaling_mode.get_ec2_tags(initialized_app))
    # when deactivated the buffer EC2 name has an additional -buffer suffix
    expected_tags = auto_scaling_mode.get_ec2_tags(initialized_app) | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    assert "Name" in expected_tags
    expected_tags["Name"] = TypeAdapter(AWSTagValue).validate_python(str(expected_tags["Name"]) + "-buffer")
    assert expected_tags == deactivated_buffer_tags


@pytest.mark.parametrize(
    "tags, expected_is_buffer",
    [
        ({"whatever_key": "whatever_value"}, False),
        ({WARM_BUFFER_MACHINE_TAG_KEY: "whatever_value"}, True),
    ],
)
def test_is_buffer_machine(tags: EC2Tags, expected_is_buffer: bool):
    assert is_warm_buffer_machine(tags) is expected_is_buffer


def test_ec2_warm_buffer_startup_script_logs_in_before_warming_up(app_environment: EnvVarsDict):
    app_settings = ApplicationSettings.create_from_envs()
    assert app_settings.AUTOSCALING_REGISTRY
    boot_specific = EC2InstanceBootSpecific(ami_id="ami-0123456789abcdef0", pre_pull_images=["nginx:latest"])

    steps = ec2_warm_buffer_startup_script(boot_specific, app_settings).split(" && ")

    # the machine is not in the swarm yet here, so a failing login costs nothing but a replaced machine
    assert steps[0].startswith("( "), f"expected the login to retry in a subshell, got {steps[0]}"
    assert " docker login " in steps[0], f"expected the machine to log in before warming up, got {steps[0]}"


def test_ec2_warm_buffer_startup_script_without_pre_pulling_skips_the_login(app_environment: EnvVarsDict):
    app_settings = ApplicationSettings.create_from_envs()
    boot_specific = EC2InstanceBootSpecific(ami_id="ami-0123456789abcdef0")

    assert ec2_warm_buffer_startup_script(boot_specific, app_settings) == ""
