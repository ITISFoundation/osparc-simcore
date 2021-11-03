# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pathlib import Path

import yaml
from service_integration.yaml_utils import yaml_safe_load


def test_include_file_in_yaml(tests_data_dir: Path):

    expected = yaml.safe_load((tests_data_dir / "compose-spec.yml").read_text())

    with open(tests_data_dir / "service.yml") as fh:
        data = yaml_safe_load(fh)

    # compose-spec: !include ./compose-spec.yml
    assert data["compose-spec"] == expected
