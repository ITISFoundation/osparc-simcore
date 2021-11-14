import json
import pathlib
from pathlib import Path
from typing import Dict

import pydantic.json
import pytest
import yaml
from service_integration.osparc_config import IOSpecification, ServiceSpecification

pydantic.json.ENCODERS_BY_TYPE[pathlib.PosixPath] = str


@pytest.fixture
def labels_annotations(tests_data_dir: Path, setup: str):
    data = yaml.safe_load((tests_data_dir / "docker-compose-meta.yml").read_text())

    service_name = {
        "legacy": "dy-static-file-server",
        "service-sidecared": "dy-static-file-server-dynamic-sidecar",
        "compose-sidecared": "dy-static-file-server-dynamic-sidecar-compose-spec",
    }

    labels = data["services"][service_name[setup]]["build"]["labels"]

    # patch -> replaces some environs
    if compose_spec := labels.get("simcore.service.compose-spec"):
        if compose_spec == "${DOCKER_COMPOSE_SPECIFICATION}":
            labels["simcore.service.compose-spec"] = json.dumps(
                yaml.safe_load((tests_data_dir / "compose-spec.yml").read_text())
            )
    return labels


@pytest.mark.parametrize("setup", ["legacy", "service-sidecared", "compose-sidecared"])
def test_load_from_labels(
    labels_annotations: Dict[str, str], setup: str, tmp_path: Path
):
    io_spec = IOSpecification.from_labels_annotations(labels_annotations)
    service_spec = ServiceSpecification.from_labels_annotations(labels_annotations)

    print(io_spec.json(exclude_unset=True, indent=2))
    print(service_spec.json(exclude_unset=True, indent=2))

    # create yamls from config
    for model in (service_spec, io_spec):
        config_path = tmp_path / f"{model.__class__.__name__.lower()}-{setup}.yml"
        with open(config_path, "wt") as fh:
            data = json.loads(
                model.json(exclude_unset=True, by_alias=True, exclude_none=True)
            )
            yaml.safe_dump(data, fh, sort_keys=False)

        # reload from yaml and compare
        new_model = model.__class__.from_yaml(config_path)
        assert new_model == model
