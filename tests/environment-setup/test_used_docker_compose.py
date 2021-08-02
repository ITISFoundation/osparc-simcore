# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import re
import shutil
import subprocess
import sys
from itertools import chain
from pathlib import Path
from typing import List, Set, Tuple

import pytest
import yaml


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
def docker_compose_in_ci_scripts(osparc_simcore_root_dir: Path) -> Tuple[Path, str]:
    ci_workflows_path = osparc_simcore_root_dir / ".github/workflows"
    versions_in_workflow_files: Set[str] = set()
    for workflow_file in ci_workflows_path.rglob("*.yml"):
        versions_in_file: Set[str] = {
            found.group(1)
            for found in re.finditer(
                r"docker_compose: \[([\d\.]+)\]", workflow_file.read_text()
            )
        }
        assert (
            len(versions_in_file) == 1
        ), f"found different docker_compose versions in {workflow_file}, versions found {versions_in_file}, please check!"

        versions_in_workflow_files.update(versions_in_file)
    assert (
        len(versions_in_workflow_files) == 1
    ), f"found different docker_compose versions in workflow files: {versions_in_workflow_files}, please check {list(ci_workflows_path.rglob('*.yml'))}!"
    return (ci_workflows_path, versions_in_workflow_files.pop())


def test_all_docker_compose_have_same_version(
    docker_compose_in_requirement_files,
    docker_compose_in_ci_scripts,
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
        str(docker_compose_in_ci_scripts[0].relative_to(osparc_simcore_root_dir)),
        "->",
        docker_compose_in_ci_scripts[1],
    )
    assert (
        docker_compose_in_ci_scripts[1] == previous[1]
    ), f"CI installs {docker_compose_in_ci_scripts[1]}=!{previous[1]} (see {docker_compose_in_ci_scripts[0]}"


@pytest.fixture
def ensure_env_file(env_devel_file: Path) -> Path:
    env_path = env_devel_file.parent / ".env"
    delete = False
    if not env_path.exists():
        shutil.copy(env_devel_file, env_path)
        delete = True

    yield env_path

    if delete:
        env_path.unlink()


current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.resolve()
repo_dir = current_dir.parent.parent
compose_paths = chain(
    *[
        repo_dir.rglob(glob)
        for glob in (
            "docker-compose.yml",
            "docker-compose-ops.yml",
            "docker-compose.yml",
        )
    ]
)


@pytest.mark.parametrize(
    "compose_path", compose_paths, ids=lambda p: str(p.relative_to(repo_dir))
)
def test_validate_compose_file(
    compose_path: Path, env_devel_file: Path, ensure_env_file
):

    assert compose_path.exists()

    compose = yaml.safe_load(compose_path.read_text())
    print(
        str(compose_path.relative_to(repo_dir)), "-> version=", compose.get("version")
    )

    subprocess.run(
        f"docker-compose --file {compose_path} --env-file {env_devel_file} --verbose config",
        shell=True,
        check=True,
    )

    # About versioning https://docs.docker.com/compose/compose-file/compose-file-v3/
    assert compose["version"] == "3.8"


def test_installed_docker_compose(docker_compose_in_ci_scripts):
    setup_ci_path, ci_version = docker_compose_in_ci_scripts

    which = subprocess.run(
        "which docker-compose",
        shell=True,
        stdout=subprocess.PIPE,
        encoding="utf8",
        check=True,
    ).stdout.strip()

    p = subprocess.run(
        ["docker-compose", "--version"],
        stdout=subprocess.PIPE,
        encoding="utf8",
        check=True,
    )
    installed_version = re.search(r"\d+\.\d+\.\d+", p.stdout).group()
    assert (
        ci_version == installed_version
    ), f"Use {setup_ci_path} to install version {ci_version} of docker-compose in your system {which}"
