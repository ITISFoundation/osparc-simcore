from pathlib import Path
from typing import Any

import pytest

from .helpers.docker import run_docker_compose_config


@pytest.fixture(scope="module")
def dev_vendors_docker_compose(
    osparc_simcore_root_dir: Path,
    osparc_simcore_scripts_dir: Path,
    env_file_for_testing: Path,
    temp_folder: Path,
) -> dict[str, Any]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose-dev-vendors.yml"
    assert docker_compose_path.exists()

    return run_docker_compose_config(
        project_dir=osparc_simcore_root_dir / "services",
        scripts_dir=osparc_simcore_scripts_dir,
        docker_compose_paths=docker_compose_path,
        env_file_path=env_file_for_testing,
        destination_path=temp_folder / "ops_docker_compose.yml",
    )
