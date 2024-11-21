# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2Tags
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerGenericTag
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.constants import (
    ACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    BUFFER_MACHINE_TAG_KEY,
    DEACTIVATED_BUFFER_MACHINE_EC2_TAGS,
    PRE_PULLED_IMAGES_EC2_TAG_KEY,
)
from simcore_service_autoscaling.modules.auto_scaling_mode_computational import (
    ComputationalAutoscaling,
)
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.utils.buffer_machines_pool_core import (
    dump_pre_pulled_images_as_tags,
    get_activated_buffer_ec2_tags,
    get_deactivated_buffer_ec2_tags,
    is_buffer_machine,
    load_pre_pulled_images_from_tags,
)


def test_get_activated_buffer_ec2_tags_dynamic(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    initialized_app: FastAPI,
):
    auto_scaling_mode = DynamicAutoscaling()
    activated_buffer_tags = get_activated_buffer_ec2_tags(
        initialized_app, auto_scaling_mode
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
    auto_scaling_mode = DynamicAutoscaling()
    deactivated_buffer_tags = get_deactivated_buffer_ec2_tags(
        initialized_app, auto_scaling_mode
    )
    # when deactivated the buffer EC2 name has an additional -buffer suffix
    expected_tags = (
        auto_scaling_mode.get_ec2_tags(initialized_app)
        | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    )
    assert "Name" in expected_tags
    expected_tags[AWSTagKey("Name")] = TypeAdapter(AWSTagValue).validate_python(
        str(expected_tags[AWSTagKey("Name")]) + "-buffer"
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
    auto_scaling_mode = ComputationalAutoscaling()
    activated_buffer_tags = get_activated_buffer_ec2_tags(
        initialized_app, auto_scaling_mode
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
    auto_scaling_mode = ComputationalAutoscaling()
    deactivated_buffer_tags = get_deactivated_buffer_ec2_tags(
        initialized_app, auto_scaling_mode
    )
    # when deactivated the buffer EC2 name has an additional -buffer suffix
    expected_tags = (
        auto_scaling_mode.get_ec2_tags(initialized_app)
        | DEACTIVATED_BUFFER_MACHINE_EC2_TAGS
    )
    assert "Name" in expected_tags
    expected_tags[AWSTagKey("Name")] = TypeAdapter(AWSTagValue).validate_python(
        str(expected_tags[AWSTagKey("Name")]) + "-buffer"
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
    assert is_buffer_machine(tags) is expected_is_buffer


@pytest.mark.parametrize(
    "images, expected_tags",
    [
        pytest.param(
            [
                "itisfoundation/dynamic-sidecar:latest",
                "itisfoundation/agent:latest",
                "registry.pytest.com/simcore/services/dynamic/ti-postpro:2.0.34",
                "registry.pytest.com/simcore/services/dynamic/ti-simu:1.0.12",
                "registry.pytest.com/simcore/services/dynamic/ti-pers:1.0.19",
                "registry.pytest.com/simcore/services/dynamic/sim4life-postpro:2.0.106",
                "registry.pytest.com/simcore/services/dynamic/s4l-core-postpro:2.0.106",
                "registry.pytest.com/simcore/services/dynamic/s4l-core-stream:2.0.106",
                "registry.pytest.com/simcore/services/dynamic/sym-server-8-0-0-dy:2.0.106",
                "registry.pytest.com/simcore/services/dynamic/sim4life-8-0-0-modeling:3.2.34",
                "registry.pytest.com/simcore/services/dynamic/s4l-core-8-0-0-modeling:3.2.34",
                "registry.pytest.com/simcore/services/dynamic/s4l-stream-8-0-0-dy:3.2.34",
                "registry.pytest.com/simcore/services/dynamic/sym-server-8-0-0-dy:3.2.34",
            ],
            {
                f"{PRE_PULLED_IMAGES_EC2_TAG_KEY}_0": '["itisfoundation/dynamic-sidecar:latest","itisfoundation/agent:latest","registry.pytest.com/simcore/services/dynamic/ti-postpro:2.0.34","registry.pytest.com/simcore/services/dynamic/ti-simu:1.0.12","registry.pytest.com/simcore/services/dynamic/ti-pers:1.0.',
                f"{PRE_PULLED_IMAGES_EC2_TAG_KEY}_1": '19","registry.pytest.com/simcore/services/dynamic/sim4life-postpro:2.0.106","registry.pytest.com/simcore/services/dynamic/s4l-core-postpro:2.0.106","registry.pytest.com/simcore/services/dynamic/s4l-core-stream:2.0.106","registry.pytest.com/simcore/services',
                f"{PRE_PULLED_IMAGES_EC2_TAG_KEY}_2": '/dynamic/sym-server-8-0-0-dy:2.0.106","registry.pytest.com/simcore/services/dynamic/sim4life-8-0-0-modeling:3.2.34","registry.pytest.com/simcore/services/dynamic/s4l-core-8-0-0-modeling:3.2.34","registry.pytest.com/simcore/services/dynamic/s4l-stream-8-0-0',
                f"{PRE_PULLED_IMAGES_EC2_TAG_KEY}_3": '-dy:3.2.34","registry.pytest.com/simcore/services/dynamic/sym-server-8-0-0-dy:3.2.34"]',
            },
            id="many images that get chunked to AWS Tag max length",
        ),
        pytest.param(
            ["itisfoundation/dynamic-sidecar:latest", "itisfoundation/agent:latest"],
            {
                PRE_PULLED_IMAGES_EC2_TAG_KEY: '["itisfoundation/dynamic-sidecar:latest","itisfoundation/agent:latest"]'
            },
            id="<256 characters jsonized number of images does not get chunked",
        ),
        pytest.param(
            [],
            {PRE_PULLED_IMAGES_EC2_TAG_KEY: "[]"},
            id="empty list",
        ),
    ],
)
def test_dump_load_pre_pulled_images_as_tags(
    images: list[DockerGenericTag], expected_tags: EC2Tags
):
    assert dump_pre_pulled_images_as_tags(images) == expected_tags
    assert load_pre_pulled_images_from_tags(expected_tags) == images


def test_load_pre_pulled_images_as_tags_no_tag_present_returns_empty_list(faker: Faker):
    assert load_pre_pulled_images_from_tags(faker.pydict(allowed_types=(str,))) == []
