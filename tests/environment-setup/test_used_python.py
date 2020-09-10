# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name


import re
from pathlib import Path
from typing import List, Tuple

import pytest


PIP_INSTALL_UPGRADE_PATTERN = re.compile(
    r"pip .* install\s+--upgrade .* pip([=~><]+)([\d\.]+)", re.DOTALL
)

PYTHON_VERSION_DOCKER_PATTERN = re.compile(r"ARG PYTHON_VERSION=\"([\d\.]+)\"")


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

    return res



def test_all_image_use_same_python_version():
    for dockerfile_path in osparc_simcore_root_dir.rglob("Dockerfile"):



def test_all_pip_have_same_version(expected_pip_version, pip_in_dockerfiles):
    for dockerfile, pip_version in pip_in_dockerfiles:
        assert (
            pip_version == expected_pip_version
        ), f"Expected {expected_pip_version} in {dockerfile}, got {pip_version}"
