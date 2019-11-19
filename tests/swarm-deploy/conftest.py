# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

import pytest
import yaml

current_dir = Path( sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def osparc_simcore_root_dir() -> Path:
    WILDCARD = "services/web/server"

    root_dir = Path(current_dir)
    while not any(root_dir.glob(WILDCARD)) and root_dir != Path("/"):
        root_dir = root_dir.parent

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


@pytest.fixture(scope='module')
def osparc_deploy(osparc_simcore_root_dir: Path) -> Dict:
    print(f'Deploying from  registry {os.environ.get("DOCKER_REGISTRY")} \
        and tag {os.environ.get("DOCKER_IMAGE_TAG")}')

    subprocess.run(
        "make down",
        shell=True, check=False,
        cwd=osparc_simcore_root_dir
    )

    subprocess.run(
        "make up-version info-swarm",
        shell=True, check=True,
        cwd=osparc_simcore_root_dir
    )

    with open( osparc_simcore_root_dir / ".stack-simcore-version.yml" ) as fh:
        simcore_config = yaml.safe_load(fh)
    with open( osparc_simcore_root_dir / ".stack-ops.yml" ) as fh:
        ops_config = yaml.safe_load(fh)

    yield {
        'simcore': simcore_config,
        'ops': ops_config
    }

    subprocess.run(
        "make down",
        shell=True, check=True,
        cwd=osparc_simcore_root_dir
    )

    (osparc_simcore_root_dir / ".stack-simcore-version.yml").unlink()
    (osparc_simcore_root_dir / ".stack-ops.yml").unlink()
