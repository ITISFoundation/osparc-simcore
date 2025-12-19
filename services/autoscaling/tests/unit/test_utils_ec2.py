# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable

import pytest
from aws_library.ec2 import AWSTagKey, EC2InstanceType, EC2Tags, Resources
from aws_library.ec2._models import EC2InstanceData
from faker import Faker
from models_library.docker import OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.core.errors import (
    ConfigurationError,
    Ec2InvalidDnsNameError,
    Ec2TagDeserializationError,
    TaskBestFittingInstanceNotFoundError,
)
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.utils.utils_ec2 import (
    _create_chunked_tag_pattern,
    closest_instance_policy,
    compose_user_data,
    dump_as_ec2_tags,
    dump_task_required_node_labels_as_tags,
    find_best_fitting_ec2_instance,
    get_ec2_tags_computational,
    get_ec2_tags_dynamic,
    list_tag_keys,
    list_task_required_node_labels_tag_keys,
    load_from_ec2_tags,
    load_task_required_docker_node_labels_from_tags,
    node_host_name_from_ec2_private_dns,
    node_ip_from_ec2_private_dns,
)


async def test_find_best_fitting_ec2_instance_with_no_instances_raises():
    # this shall raise as there are no available instances
    with pytest.raises(ConfigurationError):
        find_best_fitting_ec2_instance(
            allowed_ec2_instances=[],
            resources=Resources(cpus=0, ram=ByteSize(0)),
        )


async def test_find_best_fitting_ec2_instance_closest_instance_policy_with_resource_0_raises(
    random_fake_available_instances: list[EC2InstanceType],
):
    with pytest.raises(TaskBestFittingInstanceNotFoundError):
        find_best_fitting_ec2_instance(
            allowed_ec2_instances=random_fake_available_instances,
            resources=Resources(cpus=0, ram=ByteSize(0)),
            score_type=closest_instance_policy,
        )


@pytest.mark.parametrize(
    "needed_resources,expected_ec2_instance",
    [
        *[
            (
                Resources(cpus=n, ram=ByteSize(n)),
                EC2InstanceType(
                    name="c5ad.12xlarge", resources=Resources(cpus=n, ram=ByteSize(n))
                ),
            )
            for n in range(1, 30)
        ],
        *[
            (
                Resources(cpus=15, ram=ByteSize(128), generic_resources={"gpu": 1}),
                EC2InstanceType(
                    name="c5ad.12xlarge",
                    resources=Resources(
                        cpus=15, ram=ByteSize(128), generic_resources={"gpu": 12}
                    ),
                ),
            )
        ],
    ],
    ids=str,
)
async def test_find_best_fitting_ec2_instance_closest_instance_policy(
    needed_resources: Resources,
    expected_ec2_instance: EC2InstanceType,
    random_fake_available_instances: list[EC2InstanceType],
):
    found_instance: EC2InstanceType = find_best_fitting_ec2_instance(
        allowed_ec2_instances=random_fake_available_instances,
        resources=needed_resources,
        score_type=closest_instance_policy,
    )

    assert found_instance.resources == expected_ec2_instance.resources


def test_compose_user_data(faker: Faker):
    command = faker.text()
    user_data = compose_user_data(command)
    assert user_data.startswith("#!/bin/bash")
    assert command in user_data


@pytest.mark.parametrize(
    "aws_private_dns, expected_host_name",
    [
        ("ip-10-12-32-3.internal-data", "ip-10-12-32-3"),
        ("ip-10-12-32-32.internal-data", "ip-10-12-32-32"),
        ("ip-10-0-3-129.internal-data", "ip-10-0-3-129"),
        ("ip-10-0-3-12.internal-data", "ip-10-0-3-12"),
    ],
)
def test_node_host_name_from_ec2_private_dns(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    aws_private_dns: str,
    expected_host_name: str,
):
    instance = fake_ec2_instance_data(
        aws_private_dns=aws_private_dns,
    )
    assert node_host_name_from_ec2_private_dns(instance) == expected_host_name


def test_node_host_name_from_ec2_private_dns_raises_with_invalid_name(
    fake_ec2_instance_data: Callable[..., EC2InstanceData], faker: Faker
):
    instance = fake_ec2_instance_data(aws_private_dns=faker.name())
    with pytest.raises(Ec2InvalidDnsNameError):
        node_host_name_from_ec2_private_dns(instance)


@pytest.mark.parametrize(
    "aws_private_dns, expected_host_name",
    [
        ("ip-10-12-32-3.internal-data", "10.12.32.3"),
        ("ip-10-12-32-32.internal-data", "10.12.32.32"),
        ("ip-10-0-3-129.internal-data", "10.0.3.129"),
        ("ip-10-0-3-12.internal-data", "10.0.3.12"),
    ],
)
def test_node_ip_from_ec2_private_dns(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    aws_private_dns: str,
    expected_host_name: str,
):
    instance = fake_ec2_instance_data(
        aws_private_dns=aws_private_dns,
    )
    assert node_ip_from_ec2_private_dns(instance) == expected_host_name


def test_node_ip_from_ec2_private_dns_raises_with_invalid_name(
    fake_ec2_instance_data: Callable[..., EC2InstanceData], faker: Faker
):
    instance = fake_ec2_instance_data(aws_private_dns=faker.name())
    with pytest.raises(Ec2InvalidDnsNameError):
        node_ip_from_ec2_private_dns(instance)


def test_create__chunked_tag_pattern():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    pattern = _create_chunked_tag_pattern(base_key)

    # Should match single tag format
    assert pattern.match("test.key")

    # Should match chunked format
    assert pattern.match("test.key_0")
    assert pattern.match("test.key_1")
    assert pattern.match("test.key_123")

    # Should not match other keys
    assert not pattern.match("test.key.extra")
    assert not pattern.match("other.test.key")
    assert not pattern.match("test.key_")
    assert not pattern.match("test.key_abc")


def test_dump_as_ec2_tags_small_data():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    small_data = ["image:v1", "image:v2"]

    tags = dump_as_ec2_tags(small_data, base_tag_key=base_key)

    # Should create single tag
    assert len(tags) == 1
    assert "test.key" in tags
    assert "test.key_0" not in tags


def test_dump_as_ec2_tags_large_data():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    # Create data that will definitely exceed 256 chars when JSON serialized
    large_data = [f"very-long-image-name-{i}:v1.0.0-with-long-tag" for i in range(20)]

    tags = dump_as_ec2_tags(large_data, base_tag_key=base_key)

    # Should create multiple chunked tags
    assert len(tags) > 1
    assert "test.key_0" in tags
    assert "test.key_1" in tags


def test_load_from_ec2_tags_single_format():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    tags: EC2Tags = {base_key: '["image:v1", "image:v2"]'}

    result = load_from_ec2_tags(
        tags, base_tag_key=base_key, type_adapter=TypeAdapter(list[str])
    )

    assert result == ["image:v1", "image:v2"]


def test_load_from_ec2_tags_chunked_format():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    # Simulate chunked JSON
    tags: EC2Tags = {
        TypeAdapter(AWSTagKey).validate_python("test.key_0"): '["image',
        TypeAdapter(AWSTagKey).validate_python("test.key_1"): ':v1"]',
    }

    result = load_from_ec2_tags(
        tags, base_tag_key=base_key, type_adapter=TypeAdapter(list[str])
    )

    assert result == ["image:v1"]


def test_load_from_ec2_tags_empty_returns_none():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    tags: EC2Tags = {}

    result = load_from_ec2_tags(
        tags, base_tag_key=base_key, type_adapter=TypeAdapter(list[str])
    )

    assert result is None


def test_load_from_ec2_tags_malformed_raises():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    tags: EC2Tags = {base_key: "not-valid-json{"}

    with pytest.raises(Ec2TagDeserializationError):
        load_from_ec2_tags(
            tags, base_tag_key=base_key, type_adapter=TypeAdapter(list[str])
        )


def test_list_chunked_tag_keys_single_format():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    tags: EC2Tags = {
        base_key: "value",
        TypeAdapter(AWSTagKey).validate_python("other.key"): "other",
    }

    keys = list_tag_keys(tags, base_tag_key=base_key)

    assert len(keys) == 1
    assert keys[0] == base_key


def test_list_chunked_tag_keys_chunked_format():
    base_key = TypeAdapter(AWSTagKey).validate_python("test.key")
    tags: EC2Tags = {
        TypeAdapter(AWSTagKey).validate_python("test.key_0"): "chunk0",
        TypeAdapter(AWSTagKey).validate_python("test.key_1"): "chunk1",
        TypeAdapter(AWSTagKey).validate_python("test.key_2"): "chunk2",
        TypeAdapter(AWSTagKey).validate_python("other.key"): "other",
    }

    keys = list_tag_keys(tags, base_tag_key=base_key)

    assert len(keys) == 3
    assert TypeAdapter(AWSTagKey).validate_python("test.key_0") in keys
    assert TypeAdapter(AWSTagKey).validate_python("test.key_1") in keys
    assert TypeAdapter(AWSTagKey).validate_python("test.key_2") in keys


def test_dump_and_load_custom_placement_labels():
    # Use first valid label key
    valid_label = next(iter(OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS))
    labels = {valid_label: "value1", "invalid.label": "should_be_filtered"}

    tags = dump_task_required_node_labels_as_tags(labels)
    loaded_labels = load_task_required_docker_node_labels_from_tags(tags)
    tags_keys = list_task_required_node_labels_tag_keys(tags)

    # Should only contain valid labels
    assert loaded_labels == {valid_label: "value1"}
    assert "invalid.label" not in loaded_labels
    assert list(tags.keys()) == tags_keys


def test_load_custom_placement_labels_from_empty_tags():
    tags: EC2Tags = {}
    result = load_task_required_docker_node_labels_from_tags(tags)
    assert result == {}


def test_get_ec2_tags_dynamic(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    app_settings: ApplicationSettings,
):
    dynamic_tags = get_ec2_tags_dynamic(app_settings)
    assert dynamic_tags


def test_get_ec2_tags_computational(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_computational_mode: EnvVarsDict,
    app_settings: ApplicationSettings,
):
    computational_tags = get_ec2_tags_computational(app_settings)
    assert computational_tags
