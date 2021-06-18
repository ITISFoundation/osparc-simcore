# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name


import configparser
import re
import sys
from pathlib import Path
from typing import List, Tuple

import pytest
import yaml

PIP_INSTALL_UPGRADE_PATTERN = re.compile(
    r"pip .* install\s+--upgrade .* pip([=~><]+)([\d\.]+)", re.DOTALL
)

PYTHON_VERSION_DOCKER_PATTERN = re.compile(r"ARG PYTHON_VERSION=\"([\d\.]+)\"")
FROZEN_SERVICES = ["director"]


# TODO: enhance version comparison with from packaging.version from setuptools
def to_version(version: str) -> Tuple[int, ...]:
    return tuple(int(v) for v in version.split("."))


def to_str(version) -> str:
    return ".".join(map(str, version))


def make_versions_comparable(*versions) -> List[Tuple[int]]:
    vers = []
    n = 10000
    for v in versions:
        if isinstance(v, str):
            v = to_version(v)
        if len(v) < n:
            n = len(v)
        vers.append(v)
    return [v[:n] for v in vers]


@pytest.fixture(scope="session")
def expected_python_version(osparc_simcore_root_dir: Path) -> Tuple[int, ...]:
    py_version: str = (
        (osparc_simcore_root_dir / "requirements" / "PYTHON_VERSION")
        .read_text()
        .strip()
    )
    print("Expected python", py_version)
    return to_version(py_version)


@pytest.fixture(scope="session")
def expected_pip_version(osparc_simcore_root_dir: Path) -> str:
    version = None
    ref_script = osparc_simcore_root_dir / "ci/helpers/ensure_python_pip.bash"

    found = re.search(r"PIP_VERSION=([\d\.]+)", ref_script.read_text())
    assert found
    version = found.group(1)

    print(
        str(ref_script.relative_to(osparc_simcore_root_dir)),
        "->",
        version,
    )
    assert version

    return version


@pytest.fixture(scope="session")
def pip_in_dockerfiles(osparc_simcore_root_dir: Path) -> List[Tuple[Path, str]]:
    res = []
    for dockerfile_path in osparc_simcore_root_dir.rglob("Dockerfile"):
        found = PIP_INSTALL_UPGRADE_PATTERN.search(dockerfile_path.read_text())
        if found:
            # spec = found.group(1)
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
def python_in_dockerfiles(osparc_simcore_root_dir: Path) -> List[Tuple[Path, str]]:
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


def test_all_images_have_the_same_python_version(
    python_in_dockerfiles, expected_python_version
):
    for dockerfile, python_version in python_in_dockerfiles:
        if dockerfile.parent.name not in FROZEN_SERVICES:
            current_version, expected_version = make_versions_comparable(
                python_version, expected_python_version
            )
            assert (
                current_version == expected_version
            ), f"Expected python {expected_python_version} in {dockerfile}, got {python_version}"
        else:
            print(
                f"Skipping check on {dockerfile} since this service/package development was froozen "
            )


def test_running_python_version(expected_python_version):
    current_version, expected_version = make_versions_comparable(
        sys.version_info, expected_python_version
    )
    assert (
        current_version == expected_version
    ), f"Expected python {to_str(tuple(sys.version_info))} installed, got {to_str(expected_python_version)}"


def test_all_images_have_the_same_pip_version(expected_pip_version, pip_in_dockerfiles):
    for dockerfile, pip_version in pip_in_dockerfiles:
        if dockerfile.parent.name in FROZEN_SERVICES:
            print(
                "Skipping check on {dockefile} since this service/package development was froozen "
            )
        else:
            assert (
                pip_version == expected_pip_version
            ), f"Expected pip {expected_pip_version} in {dockerfile}, got {pip_version}"


def test_tooling_pre_commit_config(
    osparc_simcore_root_dir: Path, expected_python_version
):
    pre_commit_config = yaml.safe_load(
        (osparc_simcore_root_dir / ".pre-commit-config.yaml").read_text()
    )
    py_version = tuple(
        map(
            int,
            pre_commit_config["default_language_version"]["python"]
            .replace("python", "")
            .split("."),
        )
    )

    assert py_version == expected_python_version


def test_tooling_mypy_ini(osparc_simcore_root_dir: Path, expected_python_version):
    mypy_ini_path = osparc_simcore_root_dir / "mypy.ini"

    assert mypy_ini_path.exists()

    mypy_ini = configparser.ConfigParser()
    mypy_ini.read(mypy_ini_path)

    assert mypy_ini["mypy"]["python_version"] == to_str(expected_python_version)
