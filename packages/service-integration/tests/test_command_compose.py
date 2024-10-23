# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
from collections.abc import Callable
from pathlib import Path

import yaml
from service_integration.compose_spec_model import ComposeSpecification
from service_integration.osparc_config import MetadataConfig


def test_make_docker_compose_meta(
    run_program_with_args: Callable,
    docker_compose_overwrite_path: Path,
    metadata_file_path: Path,
    tmp_path: Path,
):
    """
    docker-compose-build.yml: $(metatada)
        # Injects metadata from $< as labels
        simcore-service-integrator compose --metadata $< --to-spec-file $@
    """

    target_compose_specs = tmp_path / "docker-compose.yml"
    metadata_cfg = MetadataConfig.from_yaml(metadata_file_path)

    result = run_program_with_args(
        "compose",
        "--metadata",
        str(metadata_file_path),
        "--to-spec-file",
        target_compose_specs,
    )
    assert result.exit_code == os.EX_OK, result.output

    # produces a compose spec
    assert target_compose_specs.exists()

    # valid compose specs
    compose_cfg = ComposeSpecification.model_validate(
        yaml.safe_load(target_compose_specs.read_text())
    )
    assert compose_cfg.services

    # compose labels vs metadata fild
    compose_labels = compose_cfg.services[metadata_cfg.service_name()].build.labels

    assert compose_labels
    assert isinstance(compose_labels.root, dict)

    assert (
        MetadataConfig.from_labels_annotations(compose_labels.root) == metadata_cfg
    )
