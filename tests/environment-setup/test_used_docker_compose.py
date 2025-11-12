# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from itertools import chain
from pathlib import Path

import pytest
import yaml


@pytest.fixture(scope="module")
def docker_compose_in_requirement_files(
    osparc_simcore_root_dir: Path,
) -> list[tuple[Path, str]]:
    reqs_path_version_tuples = []

    for req_path in osparc_simcore_root_dir.rglob("*.txt"):
        found = re.search(r"docker-compose==([\d\.]+)", req_path.read_text())
        if found:
            version = found.group(1)
            reqs_path_version_tuples.append((req_path, version))

    return reqs_path_version_tuples


def test_no_docker_compose_v1_in_ci_scripts(
    osparc_simcore_root_dir: Path,
):
    ci_workflows_path = osparc_simcore_root_dir / ".github/workflows"
    versions_in_workflow_files: set[str] = set()
    for workflow_file in ci_workflows_path.rglob("ci-*.yml"):
        versions_in_file: set[str] = {
            found.group(1)
            for found in re.finditer(
                r"docker_compose: \[([\d\.]+)\]", workflow_file.read_text()
            )
        }
        assert (
            len(versions_in_file) == 0
        ), f"found docker_compose versions in {workflow_file}, versions found {versions_in_file}, please check!"

        versions_in_workflow_files.update(versions_in_file)
    assert (
        len(versions_in_workflow_files) == 0
    ), f"found different docker_compose versions in workflow files: {versions_in_workflow_files}, please check {list(ci_workflows_path.rglob('ci-*.yml'))}!"


def test_there_are_no_docker_compose_v1_anywhere(
    docker_compose_in_requirement_files,
):
    assert not docker_compose_in_requirement_files


@pytest.fixture
def ensure_env_file(env_devel_file: Path) -> Iterable[Path]:
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


def _skip_not_useful_docker_composes(p) -> bool:
    result = "manual" not in f"{p}"
    result &= "tests/performance" not in f"{p}"
    return result


compose_paths = filter(
    _skip_not_useful_docker_composes,
    chain(
        *[
            repo_dir.rglob(glob)
            for glob in (
                "docker-compose.yml",
                "docker-compose-ops.yml",
            )
        ]
    ),
)


@pytest.fixture
def docker_compose_config_bash(osparc_simcore_scripts_dir: Path) -> Path:
    docker_compose_config_script = (
        osparc_simcore_scripts_dir / "docker" / "docker-stack-config.bash"
    )
    assert docker_compose_config_script.exists()
    return docker_compose_config_script


@pytest.mark.parametrize(
    "compose_path", compose_paths, ids=lambda p: str(p.relative_to(repo_dir))
)
def test_validate_compose_file(
    compose_path: Path,
    env_devel_file: Path,
    ensure_env_file: Path,
    docker_compose_config_bash: Path,
):
    assert compose_path.exists()
    compose = yaml.safe_load(compose_path.read_text())
    print(str(compose_path.relative_to(repo_dir)))

    # NOTE: with docker stack config, the .env file MUST be alongside the docker-compose file

    subprocess.run(  # noqa: S602
        " ".join(
            [
                f"{docker_compose_config_bash}",
                "-e",
                f"{env_devel_file}",
                f"{compose_path}",
            ]
        ),
        shell=True,
        check=True,
        capture_output=True,
    )

    # About versioning https://docs.docker.com/compose/compose-file/compose-file-v3/
    assert "version" not in compose


@pytest.mark.parametrize(
    "compose_path", compose_paths, ids=lambda p: str(p.relative_to(repo_dir))
)
def test_network_names_contain_only_letters_and_underscores(
    compose_path: Path,
):
    """Ensure all network names only contain letters and underscores (no hyphens or other symbols).


    NOTE: Our docker compose cannot resolve network names with hyphens

    e.g. `make .stack-simcore-development.yml` produces a compose file that do not include these networks which
    results in an error when the stack starts that prints something like

    ERROR: failed to create service master-simcore_docker-api-proxy: Error response from daemon: network master-simcore_docker-api-network not found
    """
    assert compose_path.exists()
    compose = yaml.safe_load(compose_path.read_text())

    networks = compose.get("networks", {})

    for network_name in networks:
        assert re.match(
            r"^[a-zA-Z_]+$", network_name
        ), f"Network name '{network_name}' in {compose_path.relative_to(repo_dir)} contains invalid characters. Only letters and underscores are allowed."
