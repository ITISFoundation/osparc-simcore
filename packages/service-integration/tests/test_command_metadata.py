# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from service_integration.cli._metadata import TargetVersionChoices


@pytest.fixture
def current_metadata(
    metadata_file_path: Path, target_version: str, current_version: str
) -> dict:

    metadata = yaml.safe_load(metadata_file_path.read_text())
    metadata[target_version] = current_version

    metadata_file_path.write_text(yaml.safe_dump(metadata))
    return metadata


BUMP_PARAMS = [
    # "upgrade,current_version,new_version",
    ("patch", "1.1.1", "1.1.2"),
    ("minor", "1.1.1", "1.2.0"),
    ("major", "1.1.1", "2.0.0"),
]


CMD_PARAMS = [
    (t.value, b, c, n) for t in TargetVersionChoices for b, c, n in BUMP_PARAMS
]


@pytest.mark.parametrize("target_version,bump,current_version,new_version", CMD_PARAMS)
def test_make_version(
    target_version: str,
    bump: str,
    current_version: str,
    new_version: str,
    current_metadata: dict,
    metadata_file_path: Path,
    run_program_with_args: Callable,
):
    """
    As Makefile recipe:

        version-service-patch version-service-minor version-service-major: $(metatada) ## kernel/service versioning as patch
                simcore-service-integrator bump-version --metadata-file $<  --upgrade $(subst version-service-,,$@)
    """
    # ensures current_metadata fixture worked as expected
    assert current_metadata[target_version] == current_version

    result = run_program_with_args(
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


@pytest.mark.parametrize(
    "cmd,expected_output",
    [
        (
            "simcore-service-integrator get-version --metadata-file tests/data/metadata.yml",
            "1.1.0",
        ),
        (
            "simcore-service-integrator get-version --metadata-file tests/data/metadata.yml integration-version",
            "1.0.0",
        ),
        (
            "simcore-service-integrator get-version --metadata-file tests/data/metadata.yml version",
            "1.1.0",
        ),
    ],
)
def test_get_version_from_metadata(
    cmd,
    expected_output,
    metadata_file_path: Path,
    run_program_with_args: Callable,
):
    cmd = cmd.replace("tests/data/metadata.yml", str(metadata_file_path))
    result = run_program_with_args(*cmd.split()[1:])
    assert result.exit_code == os.EX_OK, result.output

    assert result.output == expected_output


def test_changes_in_metadata_keeps_keys_order(
    metadata_file_path, run_program_with_args
):

    before = yaml.safe_load(metadata_file_path.read_text())
    print(before)

    assert before["version"] == "1.1.0"

    result = run_program_with_args(
        "bump-version",
        "--metadata-file",
        metadata_file_path,
        "--upgrade",
        "major",
    )
    assert result.exit_code == os.EX_OK, result.output

    after = yaml.safe_load(metadata_file_path.read_text())
    print(after)

    assert after["version"] == "2.0.0"

    after["version"] = "1.1.0"
    assert before == after
