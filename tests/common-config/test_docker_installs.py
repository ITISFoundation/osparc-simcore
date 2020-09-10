# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import re
import pytest
from typing import Tuple, List
from pathlib import Path


@pytest.fixture(scope="module")
def reqs_versions(osparc_simcore_root_dir: Path) -> List[Tuple[Path, str]]:
    reqs_path_version_tuples = []
    for req_path in osparc_simcore_root_dir.rglob("*.txt"):
        found = re.search(r"docker-compose==([\d\.]+)", req_path.read_text())
        if found:
            version = found.group(1)
            reqs_path_version_tuples.append((req_path, version))

    return reqs_path_version_tuples


@pytest.fixture(scope="module")
def ci_setup_version(osparc_simcore_root_dir: Path) -> Tuple[Path, str]:
    setup_ci = osparc_simcore_root_dir / "ci/github/helpers/setup_docker_compose.bash"

    found = re.search(r"DOCKER_COMPOSE_VERSION=\"([\d\.]+)\"", setup_ci.read_text())
    assert found, f"Expected DOCKER_COMPOSE_VERSION=x.x.x in {setup_ci}"

    version = found.group(1)
    return (setup_ci, version)


def test_all_docker_compose_same_version(
    reqs_versions, ci_setup_version, osparc_simcore_root_dir
):
    previous = reqs_versions[0]
    for req_path, docker_compose_version in reqs_versions:
        print(
            str(req_path.relative_to(osparc_simcore_root_dir)),
            "->",
            docker_compose_version,
        )
        assert docker_compose_version == previous[1]
        previous = (req_path, docker_compose_version)

    print(
        str(ci_setup_version[0].relative_to(osparc_simcore_root_dir)),
        "->",
        ci_setup_version[1],
    )
    assert (
        ci_setup_version[1] == previous[1]
    ), f"CI installs {ci_setup_version[1]}=!{previous[1]} (see {ci_setup_version[0]}"
