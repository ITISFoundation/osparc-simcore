# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from faker import Faker
from models_library.docker import (
    DockerGenericTag,
    DockerLabelKey,
    SimcoreServiceDockerLabelKeys,
)
from pydantic import ValidationError, parse_obj_as


@pytest.mark.parametrize(
    "label_key, valid",
    (
        (".com.docker.hello", False),
        ("_com.docker.hello", False),
        ("com.docker_man.hello", False),
        ("io.docker.hello", False),
        ("org.dockerproject.hello", False),
        ("com.hey-hey.hello", True),
        ("com.hey--hey.hello", False),
        ("com.hey..hey.hello", False),
        ("com.hey_hey.hello", False),
        ("node.labels.standard_worker", False),
        ("Node.labels.standard_worker", False),
        ("Node.labels.standard_worker", False),
        ("Node.labels.standardworker", False),
        ("node.labels.standardworker", True),
        ("io.simcore.auto-scaler", True),
    ),
)
def test_docker_label_key(label_key: str, valid: bool):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    if valid:
        instance = parse_obj_as(DockerLabelKey, label_key)
        assert instance
    else:
        with pytest.raises(ValidationError):
            parse_obj_as(DockerLabelKey, label_key)


@pytest.mark.parametrize(
    "image_name, valid",
    (
        ("busybox:latest", True),
        (
            "registry.osparc-master.com/simcore/services/dynamic/jupyter-smash:2.3.4",
            True,
        ),
        ("registry-1.docker.io/nginx:latest", True),
        ("registry-1.docker.io/ngin34x:latest", True),
        ("itisfoundation/dynamic-sidecar:release-github-latest", True),
        (
            "registry:5000/si.m--c_ore/services/1234/jupyter-smash:2.3.4",
            True,
        ),
        (
            "registry:5000/simcore/dyUPPER_CASE_FORBIDDEN_IN_NAME/jupyter-smash:2.3.4",
            False,
        ),
        (
            "registry:5000/si.m--c_ore/services/1234/jupyter-smash:.2.3.4",
            False,
        ),
        (
            "registry:5000/si.m--c_ore/services/1234/jupyter-smash:-2.3.4",
            False,
        ),
        (
            "registry:5000/si.m--c_ore/services/1234/jupyter-smash:_2.3.4",
            True,
        ),
        (
            "registry:5000/si.m--c_ore/services/1234/jupyter-smash:AUPPER_CASE_TAG_IS_OK_2.3.4",
            True,
        ),
        (
            "registry:5000/si.m--c_ore/services/1234/jupyter-smash:AUPPER_CASE_TAG_IS_OK_2.3.4",
            True,
        ),
        (
            f"registry:5000/si.m--c_ore/services/1234/jupyter-smash:{'A'*128}",
            True,
        ),
        (
            f"registry:5000/si.m--c_ore/services/1234/jupyter-smash:{'A'*129}",
            False,
        ),
    ),
)
def test_docker_generic_tag(image_name: str, valid: bool):
    if valid:
        instance = parse_obj_as(DockerGenericTag, image_name)
        assert instance
    else:
        with pytest.raises(ValidationError):
            parse_obj_as(DockerGenericTag, image_name)


@pytest.fixture
def osparc_docker_label_keys(
    faker: Faker,
) -> SimcoreServiceDockerLabelKeys:
    return SimcoreServiceDockerLabelKeys.parse_obj(
        dict(user_id=faker.pyint(), project_id=faker.uuid4(), node_id=faker.uuid4())
    )


def test_osparc_docker_label_keys_to_docker_labels(
    osparc_docker_label_keys: SimcoreServiceDockerLabelKeys,
):
    exported_dict = osparc_docker_label_keys.to_docker_labels()
    assert all(isinstance(v, str) for v in exported_dict.values())
    assert parse_obj_as(SimcoreServiceDockerLabelKeys, exported_dict)
