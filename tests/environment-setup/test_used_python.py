# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name


import re
import sys
from pathlib import Path
from typing import List, Tuple


import pytest

PIP_INSTALL_UPGRADE_PATTERN = re.compile(
    r"pip .* install\s+--upgrade .* pip([=~><]+)([\d\.]+)", re.DOTALL
)

PYTHON_VERSION_DOCKER_PATTERN = re.compile(r"ARG PYTHON_VERSION=\"([\d\.]+)\"")

# TODO: enhance version comparison with from packaging.version from setuptools

def to_version(version: str) -> Tuple[int]:
    return tuple(int(v) for v in version.split("."))


def to_str(version: Tuple[int]) -> str:
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
def expected_pip_version(osparc_simcore_root_dir: Path) -> str:
    ref_script = osparc_simcore_root_dir / "ci/helpers/ensure_python_pip.bash"
    found = re.search(r"PIP_VERSION=([\d\.]+)", ref_script.read_text())
    if found:
        version = found.group(1)

    print(
        str(ref_script.relative_to(osparc_simcore_root_dir)),
        "->",
        version,
    )
    assert found and version
    return version


@pytest.fixture(scope="session")
def expected_python_version() -> Tuple[int]:
    return (3, 6)


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


def test_all_image_use_same_python_version(
    python_in_dockerfiles, expected_python_version
):
    for dockerfile, python_version in python_in_dockerfiles:
        current_version, expected_version = make_versions_comparable(
            python_version, expected_python_version
        )
        assert (
            current_version == expected_version
        ), f"Expected python {expected_python_version} in {dockerfile}, got {python_version}"


def test_running_python_version(expected_python_version):
    current_version, expected_version = make_versions_comparable(
        sys.version_info, expected_python_version
    )
    assert (
        current_version == expected_version
    ), f"Expected python {to_str(sys.version_info)} installed, got {to_str(expected_python_version)}"


def test_all_pip_have_same_version(expected_pip_version, pip_in_dockerfiles):
    for dockerfile, pip_version in pip_in_dockerfiles:
        assert (
            pip_version == expected_pip_version
        ), f"Expected pip {expected_pip_version} in {dockerfile}, got {pip_version}"
