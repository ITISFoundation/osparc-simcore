# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name


import configparser
import re
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml
from packaging.version import Version

PIP_INSTALL_UPGRADE_PATTERN = re.compile(r"pip .* install\s+--upgrade .* pip([=~><]+)([\d\.]+)", re.DOTALL)

PYTHON_VERSION_DOCKER_PATTERN = re.compile(r"ARG PYTHON_VERSION=\"([\d\.]+)\"")
FROZEN_SERVICES = ["director"]


type VersionTuple = tuple[int, ...]
type VersionInput = str | VersionTuple


def to_version(version: str) -> VersionTuple:
    return Version(version).release


def to_str(version: Sequence[object]) -> str:
    return ".".join(map(str, version))


def _to_release(version: VersionInput) -> VersionTuple:
    if isinstance(version, str):
        return to_version(version)
    return version


def make_versions_comparable(*versions: VersionInput) -> list[VersionTuple]:
    releases = [_to_release(version) for version in versions]
    shortest_release = min(len(release) for release in releases)
    return [release[:shortest_release] for release in releases]


@pytest.fixture(scope="session")
def expected_python_version(osparc_simcore_root_dir: Path) -> tuple[int, ...]:
    py_version: str = (osparc_simcore_root_dir / "requirements" / "PYTHON_VERSION").read_text().strip()
    print("Expected python", py_version)
    return to_version(py_version)


type PathVersionTuple = tuple[Path, str]


@pytest.fixture(scope="session")
def pip_in_dockerfiles(osparc_simcore_root_dir: Path) -> list[PathVersionTuple]:
    res = []
    for dockerfile_path in osparc_simcore_root_dir.rglob("Dockerfile"):
        found = PIP_INSTALL_UPGRADE_PATTERN.search(dockerfile_path.read_text())
        if found:
            _operator = found.group(1)  # != or < or ~=
            version = found.group(2)
            print(
                str(dockerfile_path.relative_to(osparc_simcore_root_dir)),
                "->",
                version,
            )
            res.append((dockerfile_path, version))

    assert res
    return res


@pytest.fixture(scope="session")
def python_in_dockerfiles(osparc_simcore_root_dir: Path) -> list[PathVersionTuple]:
    res = []
    for dockerfile_path in osparc_simcore_root_dir.rglob("Dockerfile"):
        found = PYTHON_VERSION_DOCKER_PATTERN.search(dockerfile_path.read_text())
        if found:
            version = found.group(1)
            print(
                str(dockerfile_path.relative_to(osparc_simcore_root_dir)),
                "->",
                version,
            )
            res.append((dockerfile_path, version))
    assert res
    return res


def test_all_images_have_the_same_python_version(python_in_dockerfiles, expected_python_version: tuple[int, ...]):
    for dockerfile, python_version in python_in_dockerfiles:
        if dockerfile.parent.name not in FROZEN_SERVICES:
            current_version, expected_version = make_versions_comparable(python_version, expected_python_version)
            assert current_version == expected_version, (
                f"Expected python {expected_python_version} in {dockerfile}, got {python_version}"
            )
        else:
            print(f"Skipping check on {dockerfile} since this service/package development was frozen ")


def test_running_python_version(expected_python_version: tuple[int, ...]):
    running_python_version = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    current_version, expected_version = make_versions_comparable(running_python_version, expected_python_version)
    assert current_version == expected_version, (
        f"Expected python {to_str(tuple(sys.version_info))} installed, got {to_str(expected_python_version)}"
    )


def test_tooling_pre_commit_config(osparc_simcore_root_dir: Path, expected_python_version: tuple[int, ...]):
    pre_commit_config = yaml.safe_load((osparc_simcore_root_dir / ".pre-commit-config.yaml").read_text())
    py_version = tuple(
        map(
            int,
            pre_commit_config["default_language_version"]["python"].replace("python", "").split("."),
        )
    )

    assert py_version == expected_python_version


def test_tooling_mypy_ini(osparc_simcore_root_dir: Path, expected_python_version: tuple[int, ...]):
    mypy_ini_path = osparc_simcore_root_dir / "mypy.ini"

    assert mypy_ini_path.exists()

    mypy_ini = configparser.ConfigParser()
    mypy_ini.read(mypy_ini_path)

    assert mypy_ini["mypy"]["python_version"] == to_str(expected_python_version)
