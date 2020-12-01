import os

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from pathlib import Path
from typing import Callable, Dict

import pytest
import yaml
from pkg_resources import parse_version
from service_integration.scripts.metadata import (
    TARGET_VERSION_CHOICES,
    bump_version_string,
)


def test_pep404_compare_versions():
    # TODO: replace pkg_resources with https://importlib-metadata.readthedocs.io/en/latest/index.html so it is standard in 3.8

    # A reminder from https://setuptools.readthedocs.io/en/latest/userguide/distribution.html#specifying-your-project-s-version
    assert parse_version("1.9.a.dev") == parse_version("1.9a0dev")
    assert parse_version("2.1-rc2") < parse_version("2.1")
    assert parse_version("0.6a9dev-r41475") < parse_version("0.6a9")

    # same release but one is pre-release
    assert (
        parse_version("2.1-rc2").release == parse_version("2.1").release
        and ("2.1-rc2").is_prelease
    )


BUMP_PARAMS = [
    # "upgrade,current_version,new_version",
    ("patch", "1.1.1", "1.1.2"),
    ("minor", "1.1.1", "1.2.0"),
    ("major", "1.1.1", "2.0.0"),
]


@pytest.mark.parametrize(
    "bump,current_version,new_version",
    BUMP_PARAMS,
)
def test_bump_version_string(
    bump: str,
    current_version: str,
    new_version: str,
):
    assert bump_version_string(current_version, bump) == new_version


@pytest.fixture
def current_metadata(
    metadata_file_path: Path, target_version: str, current_version: str
) -> Dict:

    metadata = yaml.safe_load(metadata_file_path.read_text())
    metadata[target_version] = current_version

    metadata_file_path.write_text(yaml.safe_dump(metadata))
    return metadata


CMD_PARAMS = [(t, b, c, n) for t in TARGET_VERSION_CHOICES for b, c, n in BUMP_PARAMS]


@pytest.mark.parametrize("target_version,bump,current_version,new_version", CMD_PARAMS)
def test_make_version(
    target_version: str,
    bump: str,
    current_version: str,
    new_version: str,
    run_simcore_service_integrator: Callable,
    current_metadata: Dict,
    metadata_file_path: Path,
):
    """
    version-service-patch version-service-minor version-service-major: $(metatada) ## kernel/service versioning as patch
            simcore-service-integrator bump-version --metadata-file $<  --upgrade $(subst version-service-,,$@)
    """
    # ensures current_metadata fixture worked as expected
    assert current_metadata[target_version] == current_version

    result = run_simcore_service_integrator(
        "bump-version",
        "--metadata-file",
        str(metadata_file_path),
        "--upgrade",
        bump,
        target_version,
    )
    assert result.exit_code == os.EX_OK, result.output

    # version was updated in metadata file
    new_metadata = yaml.safe_load(metadata_file_path.read_text())
    assert new_metadata[target_version] == new_version

    # Did affect otherwise metadata file
    assert new_metadata.keys() == current_metadata.keys()

    new_metadata.pop(target_version)
    current_metadata.pop(target_version)
    assert new_metadata == current_metadata
