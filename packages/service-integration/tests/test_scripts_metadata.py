import os

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from pathlib import Path
from typing import Callable

import pytest
import yaml


@pytest.mark.parametrize(
    "upgrade,current_version,new_version",
    [
        ("patch", "1.1.0", "1.1.1"),
        ("minor", "1.1.0", "1.2.0"),
        ("major", "1.1.0", "2.1.0"),
    ],
)
def test_make_version_service(
    upgrade: str,
    current_version: str,
    new_version: str,
    run_simcore_service_integrator: Callable,
    metadata_file_path: Path,
):
    """
    version-service-patch version-service-minor version-service-major: $(metatada) ## kernel/service versioning as patch
            simcore-service-integrator bump-version --metadata-file $<  --upgrade $(subst version-service-,,$@)
    """
    version_key = "version"

    assert (
        yaml.safe_load(metadata_file_path.read_text())[version_key] == current_version
    )

    result = run_simcore_service_integrator(
        "bump-version",
        "--metadata-file",
        str(metadata_file_path),
        "--upgrade",
        upgrade,
        "version",
    )
    assert result.exit_code == os.EX_OK, result.output

    after = yaml.safe_load(metadata_file_path.read_text())[version_key]
    assert after == new_version
