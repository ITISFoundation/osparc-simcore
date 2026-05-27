# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import secrets
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from pydantic import ValidationError
from service_integration.compose_spec_model import Service, ServiceVolume
from service_integration.osparc_config import PathMappingsLabel, RuntimeConfig, SettingsItem


def test_create_runtime_spec_impl(tests_data_dir: Path):
    # have spec on how to run -> assemble mounts, network etc of the compose -> ready to run with `docker compose up`
    # run-spec for devel, prod, etc ...

    osparc_spec: dict = yaml.safe_load((tests_data_dir / "runtime.yml").read_text())

    pm_spec1 = PathMappingsLabel.model_validate(osparc_spec["paths-mapping"])
    pm_spec2 = PathMappingsLabel.model_validate(
        {
            "outputs_path": "/outputs",
            "inputs_path": "/inputs",
            "state_paths": ["/workdir1", "/workdir2"],
        }
    )

    pm_spec = secrets.choice([pm_spec1, pm_spec2])

    # A develop mode --

    pid = Path(f"{uuid4()}")
    nid = f"{uuid4()}"

    volumes = [
        ServiceVolume(
            type="bind",
            source=f"{pid / nid / 'inputs'}",
            target=f"{pm_spec.inputs_path}",
            read_only=True,
        ),
        ServiceVolume(
            type="bind",
            source=f"{pid / nid / 'outputs'}",
            target=f"{pm_spec.outputs_path}",
        ),
    ]

    volumes += [
        ServiceVolume(
            type="bind",
            source=f"{pid / nid / 'state' / workdir.name}",
            target=f"{workdir}",
        )
        for workdir in pm_spec.state_paths
    ]

    # FIXME: ensure all sources are different! (e.g. a/b/c  and z/c have the same name!)  # noqa: FIX001

    print(Service(volumes=volumes).model_dump_json(exclude_unset=True, indent=2))

    # TODO: _auto_map_to_service(osparc_spec["settings"])  # noqa: FIX002
    data = {}
    for obj in osparc_spec["settings"]:
        item = SettingsItem.model_validate(obj)

        if item.name == "resources":
            # https://docs.docker.com/compose/compose-file/compose-file-v3/#resources
            data["deploy"] = {
                "resources": {
                    "limits": {
                        "cpu": item.value["mem_limit"],
                        "memory": item.value["cpu_limit"],
                    }
                }
            }
        elif item.name == "ports":
            # https://docs.docker.com/compose/compose-file/compose-file-v3/#ports
            data["ports"] = [
                item.value,
            ]
        elif item.name == "constraints":
            # "https://docs.docker.com/compose/compose-file/compose-file-v3/#placement"
            data["deploy"] = {"placement": {"constraints": item.value}}

        else:
            raise AssertionError(item)

    print(Service(**data).model_dump_json(exclude_unset=True, indent=2))


def test_compatibility():
    pass


def test_upgrade():
    pass


def test_inactivity_service_not_in_compose_spec_rejected():
    """Regression: inactivity.service='container' was not validated against
    compose-spec services, causing KeyError at runtime in dynamic-sidecar."""

    runtime_data = {
        "paths-mapping": {
            "inputs_path": "/inputs",
            "outputs_path": "/outputs",
            "state_paths": ["/workspace"],
        },
        "compose-spec": {
            "version": "3.7",
            "services": {
                "jupyter-math": {
                    "image": "local/jupyter-math:1.0.0",
                }
            },
        },
        "container-http-entrypoint": "jupyter-math",
        "callbacks-mapping": {
            "inactivity": {
                "service": "container",
                "command": "cat /tmp/inactivity.json",
                "timeout": 1,
            }
        },
    }

    with pytest.raises(ValidationError, match="not found in compose-spec services"):
        RuntimeConfig.model_validate(runtime_data)


def test_inactivity_service_without_compose_spec_must_use_default_name():
    """When compose-spec is omitted (single-service), callback services
    must reference DEFAULT_SINGLE_SERVICE_NAME='container'."""

    runtime_data = {
        "paths-mapping": {
            "inputs_path": "/inputs",
            "outputs_path": "/outputs",
            "state_paths": ["/workspace"],
        },
        "callbacks-mapping": {
            "inactivity": {
                "service": "wrong-name",
                "command": "cat /tmp/inactivity.json",
                "timeout": 1,
            }
        },
    }

    with pytest.raises(ValidationError, match=r"must be 'container' when no compose-spec"):
        RuntimeConfig.model_validate(runtime_data)

    # Valid case: using "container" (default) should pass
    runtime_data["callbacks-mapping"]["inactivity"]["service"] = "container"
    instance = RuntimeConfig.model_validate(runtime_data)
    assert instance.callbacks_mapping is not None
    assert instance.callbacks_mapping.inactivity is not None
    assert instance.callbacks_mapping.inactivity.service == "container"
