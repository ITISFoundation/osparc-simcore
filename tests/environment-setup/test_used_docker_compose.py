# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import re
from pathlib import Path
from typing import List, Tuple

import pytest


@pytest.fixture(scope="module")
def docker_compose_in_requirement_files(
    osparc_simcore_root_dir: Path,
) -> List[Tuple[Path, str]]:

    reqs_path_version_tuples = []

    for req_path in osparc_simcore_root_dir.rglob("*.txt"):
        found = re.search(r"docker-compose==([\d\.]+)", req_path.read_text())
        if found:
            version = found.group(1)
            reqs_path_version_tuples.append((req_path, version))

    return reqs_path_version_tuples


@pytest.fixture(scope="module")
def docker_compose_in_ci_script(osparc_simcore_root_dir: Path) -> Tuple[Path, str]:
    setup_ci = osparc_simcore_root_dir / "ci/github/helpers/setup_docker_compose.bash"

    found = re.search(r"DOCKER_COMPOSE_VERSION=\"([\d\.]+)\"", setup_ci.read_text())
    assert found, f"Expected DOCKER_COMPOSE_VERSION=x.x.x in {setup_ci}"

    version = found.group(1)
    return (setup_ci, version)


def test_all_docker_compose_have_same_version(
    docker_compose_in_requirement_files,
    docker_compose_in_ci_script,
    osparc_simcore_root_dir,
):
    previous = docker_compose_in_requirement_files[0]
    for req_path, docker_compose_version in docker_compose_in_requirement_files:
        print(
            str(req_path.relative_to(osparc_simcore_root_dir)),
            "->",
            docker_compose_version,
        )
        assert docker_compose_version == previous[1]
        previous = (req_path, docker_compose_version)

    print(
        str(docker_compose_in_ci_script[0].relative_to(osparc_simcore_root_dir)),
        "->",
        docker_compose_in_ci_script[1],
    )
    assert (
        docker_compose_in_ci_script[1] == previous[1]
    ), f"CI installs {docker_compose_in_ci_script[1]}=!{previous[1]} (see {docker_compose_in_ci_script[0]}"
