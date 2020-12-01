# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import os
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def compose_file_path(metadata_file_path: Path) -> Path:
    # TODO: should pass with non-existing docker-compose-meta.yml file
    compose_file_path: Path = metadata_file_path.parent / "docker-compose-meta.yml"
    assert not compose_file_path.exists()

    # minimal
    compose_file_path.write_text(
        yaml.dump({"services": {"osparc-python-runner": {"build": {"labels": {}}}}})
    )
    return compose_file_path


def test_make_docker_compose_meta(
    run_simcore_service_integrator, metadata_file_path: Path, compose_file_path: Path
):
    """
    docker-compose-meta.yml: $(metatada)
        # Injects metadata from $< as labels
        simcore-service-integrator update-compose-labels --compose $@ --metadata $<
    """

    result = run_simcore_service_integrator(
        "update-compose-labels",
        "--metadata",
        str(metadata_file_path),
        "--compose",
        compose_file_path,
    )
    assert result.exit_code == os.EX_OK

    assert compose_file_path.exists()

    compose_cfg = yaml.safe_load(compose_file_path.read_text())
    metadata_cfg = yaml.safe_load(metadata_file_path.read_text())

    # TODO: compare labels vs metadata
    service_name = metadata_cfg["key"].split("/")[-1]
    compose_labels = compose_cfg["services"][service_name]["build"]["labels"]

    assert compose_labels
    # schema of expected

    # deserialize content and should fit metadata_cfg
