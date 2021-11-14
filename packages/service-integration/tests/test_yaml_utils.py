# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import os
import shutil
from pathlib import Path

import pytest
import yaml
from service_integration.yaml_utils import yaml_safe_load

#
# NOTE: cannot create a yaml file because the pre-commit hooks fail
# to recongnize '!include'  keyword when running YAML checkers
#
YAML_BODY = """\
compose-spec: !include {0}
paths-mapping:
  inputs_path: "/config/workspace/inputs"
  outputs_path: "/config/workspace/outputs"
  state_paths:
    - "/config"
settings:
  - name: resources
    type: Resources
    value:
      mem_limit: 17179869184
      cpu_limit: 1000000000
  - name: ports
    type: int
    value: 8443
  - name: constraints
    type: string
    value:
      - node.platform.os == linux
"""


@pytest.fixture
def compose_spec_path(tests_data_dir: Path, tmp_path: Path):
    dst = tmp_path / "compose-spec.yml"
    shutil.copyfile(tests_data_dir / "compose-spec.yml", dst)
    assert dst.exists()
    return dst


@pytest.fixture
def service_config_path(tmp_path: Path, compose_spec_path):
    dirpath = tmp_path / "labels"
    dirpath.mkdir(parents=True, exist_ok=True)

    filepath = dirpath / "service-with-include.yml"
    filepath.write_text(
        YAML_BODY.format(os.path.relpath(compose_spec_path.resolve(), filepath.parent))
    )
    return filepath


def test_include_file_in_yaml(compose_spec_path: Path, service_config_path: Path):

    expected = yaml.safe_load(compose_spec_path.read_text())

    with open(service_config_path) as fh:
        data = yaml_safe_load(fh)

    # compose-spec: !include ./compose-spec.yml
    assert data["compose-spec"] == expected
