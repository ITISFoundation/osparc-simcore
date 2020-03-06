# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict

import docker
import pytest
import yaml
from docker import DockerClient

current_dir = Path( sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

def _get_ip()->str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception: #pylint: disable=W0703
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


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


@pytest.fixture(scope='session')
def docker_client() -> DockerClient:
    client = docker.from_env()
    yield client


@pytest.fixture(scope='session')
def docker_swarm_node(docker_client: DockerClient) -> None:
    # SAME node along ALL session
    docker_client.swarm.init(advertise_addr=_get_ip())
    yield  #--------------------
    assert docker_client.swarm.leave(force=True)


@pytest.fixture(scope='module')
def osparc_deploy( osparc_simcore_root_dir: Path,
                   docker_client: DockerClient,
                   docker_swarm_node) -> Dict:

    environ = dict(os.environ)
    if "TRAVIS" not in environ and "GITHUB_ACTIONS" not in environ:
        environ["DOCKER_REGISTRY"] = "local"
        environ["DOCKER_IMAGE_TAG"] = "production"

    subprocess.run(
        "make info up-version info-swarm",
        shell=True, check=True, env=environ,
        cwd=osparc_simcore_root_dir
    )

    with open( osparc_simcore_root_dir / ".stack-simcore-version.yml" ) as fh:
        simcore_config = yaml.safe_load(fh)

    with open( osparc_simcore_root_dir / ".stack-ops.yml" ) as fh:
        ops_config = yaml.safe_load(fh)

    stack_configs = {
        'simcore': simcore_config,
        'ops': ops_config
    }

    yield stack_configs #-------------------------------------------------

    WAIT_BEFORE_RETRY_SECS = 1

    subprocess.run(
        "make down",
        shell=True, check=True, env=environ,
        cwd=osparc_simcore_root_dir
    )

    subprocess.run(f"docker network prune -f", shell=True, check=False)

    for stack in stack_configs.keys():
        while True:
            online = docker_client.services.list(filters={"label":f"com.docker.stack.namespace={stack}"})
            if online:
                print(f"Waiting until {len(online)} services stop: {[s.name for s in online]}")
                time.sleep(WAIT_BEFORE_RETRY_SECS)
            else:
                break

        while True:
            networks = docker_client.networks.list(filters={"label":f"com.docker.stack.namespace={stack}"})
            if networks:
                print(f"Waiting until {len(networks)} networks stop: {[n.name for n in networks]}")
                time.sleep(WAIT_BEFORE_RETRY_SECS)
            else:
                break

    # make down might delete these files
    def _safe_unlink(file_path: Path):
        # TODO: in py 3.8 it will simply be file_path.unlink(missing_ok=True)
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass

    _safe_unlink(osparc_simcore_root_dir / ".stack-simcore-version.yml")
    _safe_unlink(osparc_simcore_root_dir / ".stack-ops.yml")
