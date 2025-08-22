# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any
from uuid import UUID

import pytest
from faker import Faker
from models_library.docker import (
    DockerGenericTag,
    DockerLabelKey,
)
from models_library.services_metadata_runtime import (
    _SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX,
    SimcoreContainerLabels,
)
from pydantic import ByteSize, TypeAdapter, ValidationError

_faker = Faker()


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
        ("Node.labels.standardworker", False),
        ("node.labels.standardworker", True),
        ("io.simcore.auto-scaler", True),
    ),
)
def test_docker_label_key(label_key: str, valid: bool):
    # NOTE: https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
    if valid:
        instance = TypeAdapter(DockerLabelKey).validate_python(label_key)
        assert instance
    else:
        with pytest.raises(ValidationError):
            TypeAdapter(DockerLabelKey).validate_python(label_key)


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
            f"registry:5000/si.m--c_ore/services/1234/jupyter-smash:{'A' * 128}",
            True,
        ),
        (
            f"registry:5000/si.m--c_ore/services/1234/jupyter-smash:{'A' * 129}",
            False,
        ),
    ),
)
def test_docker_generic_tag(image_name: str, valid: bool):
    if valid:
        instance = TypeAdapter(DockerGenericTag).validate_python(image_name)
        assert instance
    else:
        with pytest.raises(ValidationError):
            TypeAdapter(DockerGenericTag).validate_python(image_name)


@pytest.mark.parametrize(
    "obj_data",
    SimcoreContainerLabels.model_config["json_schema_extra"]["examples"],
    ids=str,
)
def test_simcore_service_docker_label_keys(obj_data: dict[str, Any]):
    simcore_service_docker_label_keys = SimcoreContainerLabels.model_validate(obj_data)
    exported_dict = simcore_service_docker_label_keys.to_simcore_runtime_docker_labels()
    assert all(isinstance(v, str) for v in exported_dict.values()), (
        "docker labels must be strings!"
    )
    assert all(
        key.startswith(_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX) for key in exported_dict
    )
    re_imported_docker_label_keys = TypeAdapter(SimcoreContainerLabels).validate_python(
        exported_dict
    )
    assert re_imported_docker_label_keys
    assert simcore_service_docker_label_keys == re_imported_docker_label_keys


def test_simcore_service_docker_label_keys_construction():
    simcore_service_docker_label_keys = SimcoreContainerLabels(
        user_id=8268,
        project_id=UUID("5ea24ce0-0e4d-4ee6-a3f1-e4799752a684"),
        node_id=UUID("c17c6279-23c6-412f-8826-867323a7711a"),
        product_name="osparc",
        simcore_user_agent="oePqmjQbZndJghceKRJR",
        swarm_stack_name="UNDEFINED_DOCKER_LABEL",  # NOTE: there is currently no need for this label in the comp backend
        memory_limit=ByteSize(23424324),
        cpu_limit=1.0,
    )
    assert simcore_service_docker_label_keys.cpu_limit == 1.0
